"""Tempo estimation and grid quantization."""
import numpy as np

from .notes import Note
from .settings import GRIDS


def _resultant(t: np.ndarray, period: float) -> tuple[float, float]:
    z = np.exp(2j * np.pi * t / period).mean()
    return float(abs(z)), float(np.angle(z) / (2 * np.pi) * period)


def onset_times(notes: list[Note], merge_s: float = 0.03) -> np.ndarray:
    t = np.sort(np.array([n.start for n in notes]))
    if len(t) == 0:
        return t
    keep = [t[0]]
    for x in t[1:]:
        if x - keep[-1] > merge_s:
            keep.append(x)
    return np.array(keep)


def estimate_tempo(notes: list[Note], lo: float = 60, hi: float = 180, step_beats: float = 0.25) -> tuple[float, float]:
    """Returns (bpm, phase_seconds): the beat grid is phase + k * 60/bpm / (1/step_beats)."""
    t = onset_times(notes)
    if len(t) < 4:
        return 120.0, 0.0

    def score(bpm: float) -> float:
        beat = 60.0 / bpm
        return sum(w * _resultant(t, beat * m)[0] for w, m in ((1.0, 1.0), (0.5, 0.5), (0.25, 0.25)))

    coarse = np.arange(lo, hi + 1e-9, 0.5)
    best = max(coarse, key=score)
    fine = np.arange(best - 1, best + 1.001, 0.05)
    bpm = float(max(fine, key=score))
    _, phase = _resultant(t, 60.0 / bpm * step_beats)
    return round(bpm, 2), phase


def quantize(notes: list[Note], bpm: float, phase: float, grid: str) -> list[Note]:
    """Snap notes to the grid; times in the result are exact multiples of the grid step."""
    step = GRIDS[grid]
    beat = 60.0 / bpm
    out: list[Note] = []
    for n in notes:
        a = max(0, round(((n.start - phase) / beat) / step))
        b = round(((n.end - phase) / beat) / step)
        b = max(b, a + 1)
        out.append(Note(n.pitch, a * step * beat, b * step * beat, n.hand))
    return _fix_overlaps(out)


def _fix_overlaps(notes: list[Note]) -> list[Note]:
    """Same-pitch notes must not overlap or duplicate after snapping."""
    by_pitch: dict[int, list[Note]] = {}
    for n in sorted(notes, key=lambda n: (n.start, n.end)):
        by_pitch.setdefault(n.pitch, []).append(n)
    out: list[Note] = []
    for lst in by_pitch.values():
        kept: list[Note] = []
        for n in lst:
            if kept and n.start <= kept[-1].start:
                continue  # collapsed onto the same grid point
            if kept and kept[-1].end > n.start:
                kept[-1].end = n.start
            kept.append(n)
        out.extend(kept)
    out.sort(key=lambda n: (n.start, n.pitch))
    return out
