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


def _rect_sums(mask: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """Sum of mask inside each (xa, xb, ya, yb) box, via an integral image."""
    integral = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), np.int32)
    integral[1:, 1:] = mask.cumsum(0).cumsum(1)
    xa, xb, ya, yb = boxes.T
    return integral[yb, xb] - integral[ya, xb] - integral[yb, xa] + integral[ya, xa]


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


def label_frames(video_path: str, cal: Calibration, s: Settings, ref: np.ndarray | None = None,
                 progress: Callable[[float], None] | None = None) -> Labels:
    """Per frame, per key: 0 = off, i+1 = lit with color i. Returns (labels, pitches, fps, first_frame).

    A key counts as pressed when its sample box is mostly filled with one of the hand colors.
    """
    boxes = key_sample_boxes(cal)
    pitches = sorted(boxes)
    # box coordinates relative to the keyboard crop
    arr = np.array([(boxes[p][0] - cal.x0, boxes[p][1] - cal.x0, boxes[p][2] - cal.top, boxes[p][3] - cal.top)
                    for p in pitches])
    black = np.array([boxes[p][4] for p in pitches])
    area = (arr[:, 1] - arr[:, 0]) * (arr[:, 3] - arr[:, 2])
    hues = [h / 2 for h in (cal.hues or [])]
    tol = _hue_tolerance(cal.hues or [])

    cap = cv2.VideoCapture(str(video_path))
    fps = cal.fps
    first = int(s.start_s * fps)
    last = int(s.end_s * fps) if s.end_s else (cal.frame_count or 10**9)
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)

    kb_y0 = cal.top + int(0.75 * (cal.bottom - cal.top))
    ref_band = ref[kb_y0 : cal.bottom + 1, cal.x0 : cal.x1 + 1].astype(np.int16) if ref is not None else None

    # columns above the keyboard, used to find the seams between back-to-back notes of one key
    y_lo = max(0, cal.top - int(0.28 * cal.height))
    y_hi = max(y_lo + 20, cal.top - max(10, int(0.012 * cal.height)))
    wa = np.array([max(0, int(round(boxes[p][0] - cal.x0 - (boxes[p][1] - boxes[p][0]) / 2))) for p in pitches])
    wb = np.array([min(cal.x1 - cal.x0 + 1, int(round(boxes[p][0] - cal.x0 + (boxes[p][1] - boxes[p][0]) / 2)))
                   for p in pitches])
    wb = np.maximum(wb, wa + 1)
    # Strips just inside the left and right edges of each key's bar. A seam notches the bar's rounded
    # corners at both edges at once; a letter printed on the bar never reaches the edges.
    ww = (cal.x1 - cal.x0 + 1) / cal.n_white
    e0, e1 = lane_extents(cal, boxes, pitches, black, ref)
    inset, depth = 0.04 * ww, 0.14 * ww
    maxx = cal.x1 - cal.x0 + 1
    lw = np.clip(np.round(e0 + inset).astype(int), 0, maxx - 1)
    le = np.maximum(np.clip(np.round(e0 + depth).astype(int), 0, maxx), lw + 1)
    re = np.clip(np.round(e1 - inset).astype(int), 1, maxx)
    rs = np.minimum(np.clip(np.round(e1 - depth).astype(int), 0, maxx - 1), re - 1)
    # whole lane, for clean gaps between bars (the only seam signal that black keys' wide labels allow)
    ga = np.clip(np.round(e0 + 2).astype(int), 0, maxx - 1)
    gb = np.maximum(np.clip(np.round(e1 - 2).astype(int), 0, maxx), ga + 1)
    rows: list[np.ndarray] = []
    bottoms: list[np.ndarray] = []
    seams: dict[int, list[tuple[int, int, int]]] = {}
    n = max(1, last - first)
    for idx in range(first, last):
        ok, frame = cap.read()
        if not ok:
            break
        lab = np.zeros(len(pitches), np.uint8)
        bot = np.full(len(pitches), -1, np.int16)
        present = True
        if ref_band is not None:
            band = frame[kb_y0 : cal.bottom + 1, cal.x0 : cal.x1 + 1].astype(np.int16)
            # lit keys are a small part of the band; an intro/outro screen differs almost everywhere
            present = float((np.abs(band - ref_band).max(axis=2) < 60).mean()) > 0.5
        if present and hues:
            hsv = cv2.cvtColor(frame[cal.top : cal.bottom + 1, cal.x0 : cal.x1 + 1], cv2.COLOR_BGR2HSV)
            H = hsv[..., 0].astype(np.int16)
            lit = hsv[..., 1] >= KEY_SAT_MIN
            # black keys often have a colored sheen when idle, so demand a brighter color for them
            bright_w = lit & (hsv[..., 2] >= KEY_VAL_WHITE)
            bright_b = lit & (hsv[..., 2] >= KEY_VAL_BLACK)
            fracs = []
            for hc in hues:
                d = np.abs(H - hc)
                near = np.minimum(d, 180 - d) <= tol
                sums_w = _rect_sums(bright_w & near, arr)
                sums_b = _rect_sums(bright_b & near, arr)
                fracs.append(np.where(black, sums_b, sums_w) / area)
            fr = np.stack(fracs)
            on = fr.max(axis=0) > ON_FRACTION
            lab = np.where(on, fr.argmax(axis=0) + 1, 0).astype(np.uint8)

            reg = cv2.cvtColor(frame[y_lo:y_hi, cal.x0 : cal.x1 + 1], cv2.COLOR_BGR2HSV)
            RH = reg[..., 0].astype(np.int16)
            rbase = (reg[..., 1] >= BAR_SAT_MIN) & (reg[..., 2] >= BAR_VAL_MIN)
            bar = np.zeros(RH.shape, bool)
            for hc in hues:
                d = np.abs(RH - hc)
                bar |= rbase & (np.minimum(d, 180 - d) <= tol)
            cs = np.zeros((bar.shape[0], bar.shape[1] + 1), np.int32)
            cs[:, 1:] = bar.cumsum(axis=1)
            rowfrac = (cs[:, wb] - cs[:, wa]) / (wb - wa)  # (rows, keys)
            is_bar = rowfrac > 0.5
            has = is_bar.any(axis=0)
            bot = np.where(has, y_lo + is_bar.shape[0] - 1 - is_bar[::-1].argmax(axis=0), -1).astype(np.int16)
            side = ((cs[:, le] - cs[:, lw]) + (cs[:, re] - cs[:, rs])) / ((le - lw) + (re - rs))
            cut = max(2, (cal.top - int(SEAM_GLOW_FRAC * cal.height)) - y_lo)
            lane = (cs[:, gb] - cs[:, ga]) / (gb - ga)
            # label glyphs are white; the gap between two bars is plain background, never white
            white = (reg[..., 1] < LABEL_SAT_MAX) & (reg[..., 2] > LABEL_VAL_MIN)
            ws = np.zeros((white.shape[0], white.shape[1] + 1), np.int32)
            ws[:, 1:] = white.cumsum(axis=1)
            lane_white = (ws[:, gb] - ws[:, ga]) / (gb - ga)
            # clean gap: nothing of the bar color across the lane. Edge notch (white keys only): the
            # rounded corners of two touching bars dent both edges, while the middle stays solid.
            lo_rows = ((lane[:cut] < 0.12) & (lane_white[:cut] < 0.03)) | (~black & (side[:cut] < 0.5))
            hi_rows = (lane[:cut] > 0.5) & (black | (side[:cut] > 0.7))
            for k in np.flatnonzero(hi_rows.any(axis=0)):
                lo_k = np.flatnonzero(lo_rows[:, k])
                if not len(lo_k):
                    continue
                hi_k = hi_rows[:, k]
                splits_at = np.flatnonzero(np.diff(lo_k) > 1) + 1
                for seg in np.split(lo_k, splits_at):
                    g0, g1 = seg[0], seg[-1]
                    # a seam sits between two bars: solid bar just above and just below the dark rows
                    if (len(seg) <= MAX_SEAM_GAP and hi_k[max(0, g0 - 3) : g0].any()
                            and hi_k[g1 + 1 : g1 + 4].any()):
                        y = int(y_lo + (g0 + g1) // 2)
                        seams.setdefault(int(k), []).append((idx, y, y))
        rows.append(lab)
        bottoms.append(bot)
        if progress and (idx - first) % 100 == 0:
            progress(min((idx - first) / n, 1.0))
    cap.release()
    if not rows:
        empty = np.zeros((0, len(pitches)), np.uint8)
        return Labels(empty, pitches, fps, first, empty.astype(np.int16), {}, (y_lo, y_hi))
    return Labels(np.stack(rows), pitches, fps, first, np.stack(bottoms), seams, (y_lo, y_hi))


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
