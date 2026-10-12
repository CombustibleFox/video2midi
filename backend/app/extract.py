"""Turn the falling-note video into raw (unquantized) notes."""
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


def label_frames(video_path: str, cal: Calibration, s: Settings, ref: np.ndarray | None = None,
                 progress: Callable[[float], None] | None = None) -> tuple[np.ndarray, list[int], float, int]:
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

    rows: list[np.ndarray] = []
    n = max(1, last - first)
    for idx in range(first, last):
        ok, frame = cap.read()
        if not ok:
            break
        lab = np.zeros(len(pitches), np.uint8)
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
        rows.append(lab)
        if progress and (idx - first) % 100 == 0:
            progress(min((idx - first) / n, 1.0))
    cap.release()
    if not rows:
        return np.zeros((0, len(pitches)), np.uint8), pitches, fps, first
    return np.stack(rows), pitches, fps, first


def _runs(seq: np.ndarray) -> list[list[int]]:
    """[value, start, end_exclusive] runs."""
    change = np.flatnonzero(np.diff(seq)) + 1
    bounds = [0, *change.tolist(), len(seq)]
    return [[int(seq[a]), a, b] for a, b in zip(bounds[:-1], bounds[1:])]


def labels_to_notes(labels: np.ndarray, pitches: list[int], fps: float, first_frame: int,
                    s: Settings, n_colors: int) -> list[tuple[int, float, float, int]]:
    """Debounce each key's on/off signal. Returns (pitch, start_s, end_s, color_index)."""
    min_frames = max(1, int(np.ceil(s.min_note_s * fps)))
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
            if val and b - a >= min_frames:
                out.append((pitch, (first_frame + a) / fps, (first_frame + b) / fps, val - 1))
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
    labels, pitches, fps, first = label_frames(video_path, cal, s, ref, progress)
    raw = labels_to_notes(labels, pitches, fps, first, s, len(cal.hues or []))
    return assign_hands(raw, len(cal.hues or []), s.split_pitch)
