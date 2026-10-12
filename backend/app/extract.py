"""Turn the falling-note video into raw (unquantized) notes."""
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from .calibrate import Calibration, key_sample_boxes
from .notes import Note
from .settings import Settings

KEY_SAT_MIN = 80
KEY_VAL_WHITE = 100
KEY_VAL_BLACK = 150
ON_FRACTION = 0.6
BAR_SAT_MIN, BAR_VAL_MIN = 40, 90  # falling bars can be paler than the lit keys
LABEL_SAT_MAX, LABEL_VAL_MIN = 60, 170  # white-ish pixels: note-name labels
MAX_SEAM_GAP = 25  # px; wider gaps are real rests that the key signal already shows
MIN_SEAM_VOTES = 3  # frames that must agree on a seam
SEAM_GLOW_FRAC = 0.05  # ignore this fraction of the frame height above the keys: glow and flares live there


def _hue_tolerance(hues: list[float]) -> float:
    """Half the hue spacing (OpenCV units, 0-180), capped at 12."""
    if len(hues) < 2:
        return 12.0
    d = abs(hues[0] - hues[1])
    d = min(d, 360 - d)
    return min(12.0, d / 4)


@dataclass
class Labels:
    labels: np.ndarray  # (frames, keys): 0 off, i+1 lit with color i
    pitches: list[int]
    fps: float
    first: int  # absolute index of the first frame
    bottoms: np.ndarray  # (frames, keys): lowest bar row above the key, -1 if none
    seams: dict[int, list[tuple[int, int, int]]]  # key index -> (frame, lower bar top row, upper bar bottom row)
    seam_rows: tuple[int, int]  # absolute pixel rows (y_lo, y_hi) searched above the keyboard


def lane_extents(cal: Calibration, boxes: dict, pitches: list[int], black: np.ndarray,
                 ref: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """Left/right pixel edges (relative to the keyboard) of the bar lane of every key.

    White keys use almost their full width. Black keys sit off-center, so read their outline from the
    idle keyboard image when available.
    """
    ww = (cal.x1 - cal.x0 + 1) / cal.n_white
    centers = np.array([(boxes[p][0] + boxes[p][1]) / 2 - cal.x0 for p in pitches])
    e0 = np.where(black, centers - 0.3 * ww, centers - 0.46 * ww)
    e1 = np.where(black, centers + 0.3 * ww, centers + 0.46 * ww)
    if ref is not None:
        row = ref[cal.top + max(1, int(0.25 * (cal.bottom - cal.top))), cal.x0 : cal.x1 + 1].min(axis=1)
        dark = row < 100
        for i in np.flatnonzero(black):
            c = int(round(centers[i]))
            lo, hi = max(0, int(c - 0.45 * ww)), min(len(dark) - 1, int(c + 0.45 * ww))
            xs = np.flatnonzero(dark[lo : hi + 1]) + lo
            if len(xs) >= 3:
                e0[i], e1[i] = xs.min(), xs.max()
    return e0, e1


def _hue_intervals(hue_cv: float, tol: float) -> list[tuple[int, int]]:
    """Integer OpenCV hues within tol of hue_cv (circular), as inclusive intervals."""
    ok = [h for h in range(180) if min(abs(h - hue_cv), 180 - abs(h - hue_cv)) <= tol]
    out: list[tuple[int, int]] = []
    for h in ok:
        if out and out[-1][1] == h - 1:
            out[-1] = (out[-1][0], h)
        else:
            out.append((h, h))
    if len(out) > 1 and out[0][0] == 0 and out[-1][1] == 179:  # one interval wrapping around red
        out = [(out[-1][0], 179), (0, out[0][1])] + out[1:-1]
    return out


@dataclass
class Plan:
    """Everything the per-frame analysis needs, precomputed once. Picklable, so workers can share it."""
    pitches: list[int]
    black: np.ndarray
    hues: list[float]
    tol: float
    top: int
    bottom: int
    x0: int
    x1: int
    kb_w: int
    # lit-key detection: the pixels of every key's sample box, flattened in keyboard-crop coordinates
    flat_idx: np.ndarray
    starts: np.ndarray
    area: np.ndarray
    val_min: np.ndarray  # per pixel
    # intro/outro detection
    kb_y0: int
    ref_band: np.ndarray | None
    # bars above the keyboard
    y_lo: int
    y_hi: int
    cut: int
    bounds: np.ndarray  # sorted distinct column edges used for horizontal sums
    ix: dict[str, np.ndarray]  # name -> index of each key's boundary within `bounds`
    widths: dict[str, np.ndarray]
    bar_ranges: list[list[tuple[int, int]]]  # per hue: hue intervals


def make_plan(cal: Calibration, s: Settings, ref: np.ndarray | None) -> Plan:
    boxes = key_sample_boxes(cal)
    pitches = sorted(boxes)
    black = np.array([boxes[p][4] for p in pitches])
    kb_w, kb_h = cal.x1 - cal.x0 + 1, cal.bottom - cal.top + 1
    hues = [h / 2 for h in (cal.hues or [])]
    tol = _hue_tolerance(cal.hues or [])

    idx_parts, starts, area, vmin = [], [], [], []
    pos = 0
    for p in pitches:
        xa, xb, ya, yb, blk = boxes[p]
        xa, xb, ya, yb = xa - cal.x0, xb - cal.x0, ya - cal.top, yb - cal.top
        yy, xx = np.mgrid[ya:yb, xa:xb]
        idx_parts.append((yy * kb_w + xx).ravel())
        starts.append(pos)
        n = (xb - xa) * (yb - ya)
        area.append(n)
        vmin.append(np.full(n, KEY_VAL_BLACK if blk else KEY_VAL_WHITE, np.int16))
        pos += n

    kb_y0 = cal.top + int(0.75 * (cal.bottom - cal.top))
    ref_band = ref[kb_y0 : cal.bottom + 1, cal.x0 : cal.x1 + 1][::2, ::2].copy() if ref is not None else None

    y_lo = max(0, cal.top - int(0.28 * cal.height))
    y_hi = max(y_lo + 20, cal.top - max(10, int(0.012 * cal.height)))
    cut = max(2, (cal.top - int(SEAM_GLOW_FRAC * cal.height)) - y_lo)

    ww = kb_w / cal.n_white
    centers = np.array([(boxes[p][0] + boxes[p][1]) / 2 - cal.x0 for p in pitches])
    half = np.array([(boxes[p][1] - boxes[p][0]) / 2 for p in pitches])
    wa = np.maximum(np.round(centers - half).astype(int), 0)
    wb = np.maximum(np.minimum(kb_w, np.round(centers + half).astype(int)), wa + 1)
    e0, e1 = lane_extents(cal, boxes, pitches, black, ref)
    inset, depth = 0.04 * ww, 0.14 * ww
    lw = np.clip(np.round(e0 + inset).astype(int), 0, kb_w - 1)
    le = np.maximum(np.clip(np.round(e0 + depth).astype(int), 0, kb_w), lw + 1)
    re = np.clip(np.round(e1 - inset).astype(int), 1, kb_w)
    rs = np.minimum(np.clip(np.round(e1 - depth).astype(int), 0, kb_w - 1), re - 1)
    ga = np.clip(np.round(e0 + 2).astype(int), 0, kb_w - 1)
    gb = np.maximum(np.clip(np.round(e1 - 2).astype(int), 0, kb_w), ga + 1)

    cols = {"wa": wa, "wb": wb, "lw": lw, "le": le, "rs": rs, "re": re, "ga": ga, "gb": gb}
    bounds = np.unique(np.concatenate([v for v in cols.values()]))
    # each column edge maps to its position among the sorted distinct edges
    ix = {k: np.searchsorted(bounds, v) for k, v in cols.items()}
    widths = {"bar": wb - wa, "side": (le - lw) + (re - rs), "lane": gb - ga}
    return Plan(pitches, black, hues, tol, cal.top, cal.bottom, cal.x0, cal.x1, kb_w,
                np.concatenate(idx_parts), np.array(starts), np.array(area, float), np.concatenate(vmin),
                kb_y0, ref_band, y_lo, y_hi, cut, bounds, ix, widths,
                [_hue_intervals(h, tol) for h in hues])


def _seams_in_frame(hi_rows: np.ndarray, lo_rows: np.ndarray, idx: int, y_lo: int) -> list[tuple[int, tuple[int, int, int]]]:
    """Seams between two bars: a short run of 'gap' rows with solid bar just above and just below."""
    cut, K = lo_rows.shape
    LT, HT = lo_rows.T, hi_rows.T  # (keys, rows)
    prev = np.zeros_like(LT)
    prev[:, 1:] = LT[:, :-1]
    nxt = np.zeros_like(LT)
    nxt[:, :-1] = LT[:, 1:]
    ks, g0 = np.nonzero(LT & ~prev)  # run starts and ends come out in the same (key, row) order
    _, g1 = np.nonzero(LT & ~nxt)
    if not len(ks):
        return []
    csh = np.zeros((K, cut + 1), np.int32)
    csh[:, 1:] = HT.cumsum(axis=1)
    above = csh[ks, g0] - csh[ks, np.maximum(0, g0 - 3)] > 0
    below = csh[ks, np.minimum(cut, g1 + 4)] - csh[ks, g1 + 1] > 0
    ok = (g1 - g0 + 1 <= MAX_SEAM_GAP) & above & below
    return [(int(k), (idx, int(y_lo + (a + b) // 2), int(y_lo + (a + b) // 2)))
            for k, a, b in zip(ks[ok], g0[ok], g1[ok])]


def analyse_frame(plan: Plan, frame: np.ndarray, idx: int):
    """One frame -> (key labels, bar bottoms, seams)."""
    K = len(plan.pitches)
    lab = np.zeros(K, np.uint8)
    bot = np.full(K, -1, np.int16)
    seams: list[tuple[int, tuple[int, int, int]]] = []
    if plan.ref_band is not None:
        band = frame[plan.kb_y0 : plan.bottom + 1 : 2, plan.x0 : plan.x1 + 1 : 2]
        # lit keys are a small part of the band; an intro/outro screen differs almost everywhere
        if np.count_nonzero(cv2.absdiff(band, plan.ref_band).max(axis=2) < 60) <= 0.5 * band.shape[0] * band.shape[1]:
            return lab, bot, seams
    if not plan.hues:
        return lab, bot, seams

    bgr = frame[plan.top : plan.bottom + 1, plan.x0 : plan.x1 + 1].reshape(-1, 3)[plan.flat_idx]
    px = cv2.cvtColor(bgr.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)  # only the key boxes
    Hp = px[:, 0].astype(np.int16)
    bright = (px[:, 1] >= KEY_SAT_MIN) & (px[:, 2] >= plan.val_min)
    fracs = []
    for hc in plan.hues:
        d = np.abs(Hp - hc)
        near = np.minimum(d, 180 - d) <= plan.tol
        fracs.append(np.add.reduceat((bright & near).astype(np.int32), plan.starts) / plan.area)
    fr = np.stack(fracs)
    lab = np.where(fr.max(axis=0) > ON_FRACTION, fr.argmax(axis=0) + 1, 0).astype(np.uint8)

    reg = cv2.cvtColor(frame[plan.y_lo : plan.y_hi, plan.x0 : plan.x1 + 1], cv2.COLOR_BGR2HSV)
    bar = None
    for intervals in plan.bar_ranges:
        for lo, hi in intervals:
            m = cv2.inRange(reg, (lo, BAR_SAT_MIN, BAR_VAL_MIN), (hi, 255, 255))
            bar = m if bar is None else cv2.bitwise_or(bar, m)
    white = cv2.inRange(reg, (0, 0, LABEL_VAL_MIN + 1), (179, LABEL_SAT_MAX - 1, 255))

    def cumulative(mask: np.ndarray) -> np.ndarray:
        # per-row running count of mask pixels, read at the column edges only (via the integral image)
        integral = cv2.integral(mask, sdepth=cv2.CV_32S)
        return (integral[1:, plan.bounds] - integral[:-1, plan.bounds]) // 255

    cb, cw = cumulative(bar), cumulative(white)
    ix, wd = plan.ix, plan.widths
    rowfrac = (cb[:, ix["wb"]] - cb[:, ix["wa"]]) / wd["bar"]
    is_bar = rowfrac > 0.5
    has = is_bar.any(axis=0)
    bot = np.where(has, plan.y_lo + is_bar.shape[0] - 1 - is_bar[::-1].argmax(axis=0), -1).astype(np.int16)

    cut = plan.cut
    cb, cw = cb[:cut], cw[:cut]
    side = ((cb[:, ix["le"]] - cb[:, ix["lw"]]) + (cb[:, ix["re"]] - cb[:, ix["rs"]])) / wd["side"]
    lane = (cb[:, ix["gb"]] - cb[:, ix["ga"]]) / wd["lane"]
    lane_white = (cw[:, ix["gb"]] - cw[:, ix["ga"]]) / wd["lane"]
    # clean gap: nothing of the bar color across the lane and no white label pixels. Edge notch (white
    # keys only): the rounded corners of two touching bars dent both edges while the middle stays solid.
    lo_rows = ((lane < 0.12) & (lane_white < 0.03)) | (~plan.black & (side < 0.5))
    hi_rows = (lane > 0.5) & (plan.black | (side > 0.7))
    seams = _seams_in_frame(hi_rows, lo_rows, idx, plan.y_lo)
    return lab, bot, seams


def _open_at(video_path: str, frame: int) -> cv2.VideoCapture:
    """Open the video positioned so that the next read() returns `frame`."""
    cap = cv2.VideoCapture(str(video_path))
    if frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        if int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame:  # container can't seek exactly: decode up to it
            cap.release()
            cap = cv2.VideoCapture(str(video_path))
            for _ in range(frame):
                cap.grab()
    return cap


def _analyse_range(video_path: str, plan: Plan, a: int, b: int, on_frame=None):
    cap = _open_at(video_path, a)
    labs, bots, seams = [], [], []
    for idx in range(a, b):
        ok, frame = cap.read()
        if not ok:
            break
        lab, bot, sm = analyse_frame(plan, frame, idx)
        labs.append(lab)
        bots.append(bot)
        seams.extend(sm)
        if on_frame:
            on_frame(idx)
    cap.release()
    return labs, bots, seams


_worker: dict = {}


def _init_worker(video_path: str, plan: Plan) -> None:
    cv2.setNumThreads(1)  # one process per core already; avoid oversubscription
    _worker["video"], _worker["plan"] = video_path, plan


def _worker_chunk(a: int, b: int):
    labs, bots, seams = _analyse_range(_worker["video"], _worker["plan"], a, b)
    return a, labs, bots, seams


MIN_PARALLEL_FRAMES = 240


def auto_workers() -> int:
    import os

    return max(1, min(os.cpu_count() or 1, 8))


def label_frames(video_path: str, cal: Calibration, s: Settings, ref: np.ndarray | None = None,
                 progress: Callable[[float], None] | None = None) -> Labels:
    """Per frame, per key: 0 = off, i+1 = lit with color i, plus the bar information used to split repeats.

    A key counts as pressed when its sample box is mostly filled with one of the hand colors. Frames are
    independent of each other, so long videos are split into chunks analysed by a pool of processes.
    """
    plan = make_plan(cal, s, ref)
    fps = cal.fps
    first = int(s.start_s * fps)
    last = int(s.end_s * fps) if s.end_s else (cal.frame_count or 10**9)
    n = max(1, last - first)
    workers = s.workers if s.workers > 0 else auto_workers()
    rows_lab: list[np.ndarray] = []
    rows_bot: list[np.ndarray] = []
    seam_list: list[tuple[int, tuple[int, int, int]]] = []

    if workers <= 1 or n < MIN_PARALLEL_FRAMES:
        def on_frame(idx: int) -> None:
            if progress and (idx - first) % 100 == 0:
                progress(min((idx - first) / n, 1.0))

        rows_lab, rows_bot, seam_list = _analyse_range(video_path, plan, first, last, on_frame)
    else:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, as_completed

        size = max(60, -(-n // (workers * 4)))
        chunks = [(a, min(a + size, last)) for a in range(first, last, size)]
        results: dict[int, tuple] = {}
        done = 0
        # 'spawn' on every platform: forking a process that already runs OpenCV threads can deadlock
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_init_worker,
                                 initargs=(str(video_path), plan)) as pool:
            futures = [pool.submit(_worker_chunk, a, b) for a, b in chunks]
            for fut in as_completed(futures):
                a, labs, bots, seams = fut.result()
                results[a] = (labs, bots, seams)
                done += len(labs)
                if progress:
                    progress(min(done / n, 1.0))
        for a, b in chunks:  # reassemble in order; stop at the first chunk that ran out of video
            labs, bots, seams = results[a]
            rows_lab += labs
            rows_bot += bots
            seam_list += seams
            if len(labs) < b - a:
                break

    seams: dict[int, list[tuple[int, int, int]]] = {}
    for k, obs in sorted(seam_list, key=lambda t: (t[0], t[1][0])):
        seams.setdefault(k, []).append(obs)
    K = len(plan.pitches)
    if not rows_lab:
        empty = np.zeros((0, K), np.uint8)
        return Labels(empty, plan.pitches, fps, first, empty.astype(np.int16), {}, (plan.y_lo, plan.y_hi))
    return Labels(np.stack(rows_lab), plan.pitches, fps, first, np.stack(rows_bot), seams, (plan.y_lo, plan.y_hi))


def _runs(seq: np.ndarray) -> list[list[int]]:
    """[value, start, end_exclusive] runs."""
    change = np.flatnonzero(np.diff(seq)) + 1
    bounds = [0, *change.tolist(), len(seq)]
    return [[int(seq[a]), a, b] for a, b in zip(bounds[:-1], bounds[1:])]


def estimate_fall(L: Labels) -> tuple[float, float] | None:
    """Fall speed (px per frame) and the row where a bar's lower edge is when its key lights up.

    Fitted from the lower edge of bars approaching keys in the frames before each key lights.
    """
    steps = np.arange(3, 10)
    speeds, refs = [], []
    T, K = L.labels.shape
    for k in range(K):
        col = L.labels[:, k]
        for i in np.flatnonzero((col[1:] > 0) & (col[:-1] == 0)) + 1:
            if i < steps[-1]:
                continue
            ys = L.bottoms[i - steps, k].astype(float)
            ok = (ys >= 0) & (L.labels[i - steps, k] == 0)
            if ok.sum() < 4:
                continue
            c1, c0 = np.polyfit(steps[ok], ys[ok], 1)  # y = c0 + c1 * frames_before_light
            # tolerance of about a frame of travel: many videos repeat frames (15 fps content in 30 fps files)
            if 1 < -c1 < 120 and np.abs(c0 + c1 * steps[ok] - ys[ok]).max() <= 1.0 * -c1 + 3:
                speeds.append(-c1)
                refs.append(c0)
    if len(speeds) < 3:
        return None
    return float(np.median(speeds)), float(np.median(refs))


def seam_splits(L: Labels, fall: tuple[float, float]) -> dict[int, list[tuple[float, float]]]:
    """Per key: (note_end_frame, next_note_start_frame) for each seam between back-to-back bars."""
    spf, yref = fall
    out: dict[int, list[tuple[float, float]]] = {}
    for k, obs in L.seams.items():
        pts = sorted(((f + (yref - lower_top) / spf, f + (yref - upper_bottom) / spf, lower_top) for f, lower_top, upper_bottom in obs))
        groups: list[list[tuple[float, float, int]]] = []
        for pt in pts:
            if groups and abs(pt[0] - np.median([x[0] for x in groups[-1]])) <= 1.5:
                groups[-1].append(pt)
            else:
                groups.append([pt])
        for g in groups:
            rows = [x[2] for x in g]
            # a real seam travels down the screen as the frames advance; a fixed artifact does not
            if len(g) >= MIN_SEAM_VOTES and max(rows) - min(rows) >= 1.5 * spf:
                out.setdefault(k, []).append((float(np.median([x[0] for x in g])), float(np.median([x[1] for x in g]))))
    return out


def labels_to_notes(L: Labels, s: Settings, n_colors: int) -> list[tuple[int, float, float, int]]:
    """Debounce each key's on/off signal. Returns (pitch, start_s, end_s, color_index)."""
    labels, pitches, fps, first_frame = L.labels, L.pitches, L.fps, L.first
    min_frames = max(1, int(np.ceil(s.min_note_s * fps)))
    fall = estimate_fall(L)
    splits = seam_splits(L, fall) if fall else {}
    out = []
    for k, pitch in enumerate(pitches):
        runs = _runs(labels[:, k])
        merged: list[list[int]] = []
        for i, r in enumerate(runs):
            if (r[0] == 0 and merged and merged[-1][0] != 0 and i + 1 < len(runs)
                    and runs[i + 1][0] == merged[-1][0] and r[2] - r[1] <= s.gap_fill_frames):
                merged[-1][2] = r[2]  # bridge the dropout; the next run is absorbed below
                continue
            if merged and merged[-1][0] == r[0] and merged[-1][2] == r[1]:
                merged[-1][2] = r[2]
            else:
                merged.append(list(r))
        for val, a, b in merged:
            if not val:
                continue
            starts, ends = [float(a)], []
            for e, st in sorted(splits.get(k, [])):
                e, st = e - first_frame, st - first_frame
                if a + 1 < e < b - 1 and a < st < b and st >= e - 0.5:
                    ends.append(e)
                    starts.append(max(st, e))
            ends.append(float(b))
            for st, en in zip(starts, ends):
                if en - st >= min_frames:
                    out.append((pitch, (first_frame + st) / fps, (first_frame + en) / fps, val - 1))
    return out


def assign_hands(raw: list[tuple[int, float, float, int]], n_colors: int, split_pitch: int) -> list[Note]:
    used = sorted({c for _, _, _, c in raw})
    if n_colors >= 2 and len(used) >= 2:
        mean = {c: np.mean([p for p, _, _, cc in raw if cc == c]) for c in used}
        right = max(mean, key=mean.get)
        hand = lambda p, c: "R" if c == right else "L"
    else:
        hand = lambda p, c: "R" if p >= split_pitch else "L"
    notes = [Note(p, a, b, hand(p, c)) for p, a, b, c in raw]
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


def extract_notes(video_path: str, cal: Calibration, s: Settings, ref: np.ndarray | None = None,
                  progress: Callable[[float], None] | None = None) -> list[Note]:
    L = label_frames(video_path, cal, s, ref, progress)
    raw = labels_to_notes(L, s, len(cal.hues or []))
    return assign_hands(raw, len(cal.hues or []), s.split_pitch)
