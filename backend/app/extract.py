"""Turn the falling-note video into raw (unquantized) notes."""
from typing import Callable

import cv2
import numpy as np

from .calibrate import Calibration, key_layout
from .notes import Note
from .settings import Settings

SAT_MIN, VAL_MIN = 90, 80
ON_FRACTION = 0.6


def _hue_tolerance(hues: list[float]) -> float:
    """Half the hue spacing (OpenCV units, 0-180), capped at 12."""
    if len(hues) < 2:
        return 12.0
    d = abs(hues[0] - hues[1])
    d = min(d, 360 - d)
    return min(12.0, d / 4)


def label_frames(video_path: str, cal: Calibration, s: Settings, ref: np.ndarray | None = None,
                 progress: Callable[[float], None] | None = None) -> tuple[np.ndarray, list[int], float, int]:
    """Per frame, per key: 0 = off, i+1 = lit with color i. Returns (labels, pitches, fps, first_frame)."""
    keys = key_layout(cal)
    pitches = sorted(keys)
    xa = np.array([max(0, int(round(keys[p][0] - keys[p][1] * 0.5))) for p in pitches])
    xb = np.array([max(a + 1, int(round(keys[p][0] + keys[p][1] * 0.5))) for p, a in zip(pitches, xa)])
    hit_y = cal.top - s.hit_offset
    y0, y1 = max(0, hit_y - 1), min(cal.height, hit_y + 2)
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
            present = float((np.abs(band - ref_band).max(axis=2) < 60).mean()) > 0.5
        if present:
            hsv = cv2.cvtColor(frame[y0:y1], cv2.COLOR_BGR2HSV)
            H = hsv[..., 0].astype(np.int16)
            base = (hsv[..., 1] >= SAT_MIN) & (hsv[..., 2] >= VAL_MIN)
            fracs = []
            for hc in hues:
                d = np.abs(H - hc)
                m = base & (np.minimum(d, 180 - d) <= tol)
                cs = np.concatenate([[0], np.cumsum(m.sum(axis=0))])
                fracs.append((cs[xb] - cs[xa]) / ((y1 - y0) * (xb - xa)))
            if fracs:
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
