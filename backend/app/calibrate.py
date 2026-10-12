"""Find the keyboard, its key range, the hit line and the hand colors."""
from dataclasses import dataclass, asdict, fields

import cv2
import numpy as np

# does a black key follow the white key at this position in the octave (C D E F G A B)?
BLACK_AFTER = [1, 1, 0, 1, 1, 1, 0]
WHITE_SEMIS = [0, 2, 4, 5, 7, 9, 11]


class CalibrationError(RuntimeError):
    pass


@dataclass
class Calibration:
    width: int = 0
    height: int = 0
    fps: float = 30.0
    frame_count: int = 0
    x0: int = 0  # keyboard left/right pixel columns (inclusive)
    x1: int = 0
    top: int = 0  # keyboard top/bottom pixel rows (inclusive)
    bottom: int = 0
    n_white: int = 52
    first_midi: int = 21  # MIDI pitch of the leftmost (white) key
    hues: list[float] | None = None  # note colors as hue in degrees (0-360)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def read_info(cap: cv2.VideoCapture) -> dict:
    return {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS)) or 30.0,
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }


def sample_frames(video_path: str, n: int = 40, lo: float = 0.05, hi: float = 0.95) -> tuple[list[np.ndarray], dict]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise CalibrationError("cannot open video")
    info = read_info(cap)
    total = info["frame_count"]
    frames = []
    for i in np.linspace(lo * total, hi * total, n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            frames.append(f)
    cap.release()
    if not frames:
        raise CalibrationError("no frames could be read")
    return frames, info


def median_frame(frames: list[np.ndarray]) -> np.ndarray:
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def _longest_run(mask: np.ndarray, max_gap: int = 3) -> tuple[int, int] | None:
    best, start, last = None, None, None
    for i in np.flatnonzero(mask):
        if start is None or i - last > max_gap + 1:
            start = i
        last = i
        if best is None or last - start > best[1] - best[0]:
            best = (start, last)
    return best


def key_layout(cal: Calibration) -> dict[int, tuple[float, float]]:
    """pitch -> (center x, half width) of each visible key."""
    ww = (cal.x1 - cal.x0 + 1) / cal.n_white
    # index of the first key within the octave
    first_white = WHITE_SEMIS.index(cal.first_midi % 12) if cal.first_midi % 12 in WHITE_SEMIS else 0
    out: dict[int, tuple[float, float]] = {}
    pitch = cal.first_midi
    for i in range(cal.n_white):
        out[pitch] = (cal.x0 + (i + 0.5) * ww, ww * 0.5)
        if i == cal.n_white - 1:
            break
        if BLACK_AFTER[(first_white + i) % 7]:
            out[pitch + 1] = (cal.x0 + (i + 1) * ww, ww * 0.15)
            pitch += 2
        else:
            pitch += 1
    return out


def key_sample_boxes(cal: Calibration) -> dict[int, tuple[int, int, int, int, bool]]:
    """pitch -> (xa, xb, ya, yb, is_black): where to look for each key's lit color, in frame pixels.

    White keys are read on the lower part of the key (below the black keys), black keys on their upper
    part. Reading the keys themselves, not the falling notes, avoids the glow and sparks that many
    videos draw where the notes land.
    """
    h = cal.bottom - cal.top + 1
    ww = (cal.x1 - cal.x0 + 1) / cal.n_white
    out = {}
    for pitch, (xc, hw) in key_layout(cal).items():
        black = pitch % 12 in (1, 3, 6, 8, 10)
        if black:
            half, ya, yb = 0.12 * ww, cal.top + 0.20 * h, cal.top + 0.45 * h
        else:
            half, ya, yb = 0.30 * ww, cal.top + 0.80 * h, cal.top + 0.95 * h
        xa = max(0, int(round(xc - half)))
        xb = max(xa + 1, int(round(xc + half)))
        out[pitch] = (xa, xb, int(ya), max(int(ya) + 1, int(yb)), black)
    return out


def detect_keyboard(med: np.ndarray) -> dict:
    minc = med.min(axis=2)
    bright = minc > 170
    rowfrac = bright.mean(axis=1)
    mx = rowfrac.max()
    if mx < 0.3:
        raise CalibrationError("no keyboard found (no bright key rows)")
    run = _longest_run(rowfrac > 0.3 * mx)
    top, bottom = run
    h = bottom - top + 1
    if h < 15:
        raise CalibrationError("keyboard region too small")

    band = np.flatnonzero(rowfrac[top : bottom + 1] >= 0.85 * mx) + top
    colfrac = bright[band].mean(axis=0)
    cols = np.flatnonzero(colfrac > 0.5)
    x0, x1 = int(cols[0]), int(cols[-1])

    profile = minc[band][:, x0 : x1 + 1].mean(axis=0)
    sep = profile < 0.7 * np.median(profile)
    centers, i = [], 0
    while i < len(sep):
        if sep[i]:
            j = i
            while j + 1 < len(sep) and sep[j + 1]:
                j += 1
            centers.append((i + j) / 2 + x0)
            i = j + 1
        else:
            i += 1
    if len(centers) < 5:
        raise CalibrationError("could not find white key separators")
    ww0 = float(np.median(np.diff(centers)))
    # separators can be missed; count how many key widths each gap spans
    intervals = int(sum(max(1, round(d / ww0)) for d in np.diff(centers)))
    ww1 = (centers[-1] - centers[0]) / intervals
    n_white = max(2, int(round((x1 - x0 + 1) / ww1)))
    ww = (x1 - x0 + 1) / n_white

    # black keys: dark at the boundary between two white keys on a row near the key tops
    ya = min(bottom, top + max(1, int(0.25 * h)))
    row = minc[ya]
    has_black = []
    for i in range(1, n_white):
        bx = x0 + i * ww
        lo, hi = int(bx - 0.15 * ww), int(bx + 0.15 * ww) + 1
        has_black.append(float(row[max(lo, 0) : hi].mean()) < 100)

    best_s, best_score = 0, -1
    for s in range(7):
        score = sum(int(BLACK_AFTER[(s + i) % 7] == b) for i, b in enumerate(has_black))
        # prefer A (full 88-key boards) on ties
        if score > best_score or (score == best_score and s == 5):
            best_s, best_score = s, score

    if n_white == 52 and best_s == 5:
        first_midi = 21
    else:
        semi = WHITE_SEMIS[best_s]
        best = None
        for octave in range(0, 9):
            first = 12 * (octave + 1) + semi
            center = first + 0.85 * n_white
            if best is None or abs(center - 64) < best[0]:
                best = (abs(center - 64), first)
        first_midi = best[1]
    return dict(x0=x0, x1=x1, top=int(top), bottom=int(bottom), n_white=n_white, first_midi=int(first_midi))


def detect_hues(frames: list[np.ndarray], cal: Calibration, hit_offset: int = 4) -> list[float]:
    """Cluster saturated pixels above the keyboard by hue. Returns 1 or 2 hues (degrees)."""
    y1 = max(1, cal.top - hit_offset)
    y0 = max(0, y1 - 200)
    hues = []
    for f in frames:
        hsv = cv2.cvtColor(f[y0:y1, cal.x0 : cal.x1 + 1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
        sel = hsv[(hsv[:, 1] >= 90) & (hsv[:, 2] >= 80)]
        if len(sel) > 3000:
            sel = sel[:: len(sel) // 3000]
        hues.append(sel[:, 0].astype(np.float32) * 2.0)
    h = np.concatenate(hues) if hues else np.empty(0, np.float32)
    if len(h) < 200:
        raise CalibrationError("no colored falling notes found above the keyboard")
    ang = np.deg2rad(h)
    feats = np.stack([np.cos(ang), np.sin(ang)], axis=1).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    _, labels, centers = cv2.kmeans(feats, 2, None, crit, 5, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    cdeg = [float(np.rad2deg(np.arctan2(c[1], c[0])) % 360) for c in centers]
    sep = abs(cdeg[0] - cdeg[1])
    sep = min(sep, 360 - sep)
    frac = min(np.mean(labels == 0), np.mean(labels == 1))
    if sep < 30 or frac < 0.05:
        big = int(np.argmax(np.bincount(labels)))
        return [round(cdeg[big], 1)]
    return [round(c, 1) for c in cdeg]


def calibrate(video_path: str, n_samples: int = 40, hit_offset: int = 4):
    """Returns (Calibration, median keyboard frame, sample frames)."""
    frames, info = sample_frames(video_path, n_samples)
    med = median_frame(frames)
    kb = detect_keyboard(med)
    cal = Calibration(**info, **kb)
    cal.hues = detect_hues(frames, cal, hit_offset)
    return cal, med, frames


def render_preview(frame: np.ndarray, cal: Calibration, hit_offset: int = 4) -> np.ndarray:
    img = frame.copy()
    cv2.rectangle(img, (cal.x0, cal.top), (cal.x1, cal.bottom), (0, 255, 255), 2)
    hy = cal.top - hit_offset
    for pitch, (xa, xb, ya, yb, black) in key_sample_boxes(cal).items():
        xc = (xa + xb) / 2
        cv2.rectangle(img, (xa, ya), (xb, yb), (255, 0, 255) if black else (0, 0, 255), 1)
        if pitch % 12 == 0:
            cv2.putText(img, f"C{pitch // 12 - 1}", (int(xc) - 8, max(12, hy - 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    for i, hue in enumerate(cal.hues or []):
        bgr = cv2.cvtColor(np.uint8([[[hue / 2, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(img, (10 + i * 40, 10), (40 + i * 40, 40), bgr, -1)
        cv2.rectangle(img, (10 + i * 40, 10), (40 + i * 40, 40), (255, 255, 255), 1)
    return img
