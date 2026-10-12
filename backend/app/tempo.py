"""Tempo estimation (constant or changing) and grid quantization."""
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


class TempoMap:
    """Piecewise-linear mapping between seconds and beats.

    Anchor i says "beat B[i] happens at time T[i]"; between anchors the tempo is constant, and after the last one
    it continues at `last_bpm`. `bpms` are derived from the anchors.
    """

    def __init__(self, T, B, last_bpm: float):
        self.T = np.asarray(T, float)
        self.B = np.asarray(B, float)
        self.last_bpm = float(last_bpm)
        dt, db = np.diff(self.T), np.diff(self.B)
        self.bpms = [60.0 * b / d for b, d in zip(db, dt)] + [self.last_bpm]

    @classmethod
    def constant(cls, bpm: float, t0: float = 0.0) -> "TempoMap":
        return cls([t0], [0.0], bpm)

    @classmethod
    def from_list(cls, items: list[dict]) -> "TempoMap":
        return cls([i["time"] for i in items], [i["beat"] for i in items], items[-1]["bpm"])

    def to_list(self) -> list[dict]:
        return [{"time": round(float(t), 4), "beat": float(b), "bpm": round(float(m), 2)}
                for t, b, m in zip(self.T, self.B, self.bpms)]

    @property
    def bpm(self) -> float:
        """The tempo most of the piece is played at (by duration)."""
        if len(self.T) == 1:
            return round(self.last_bpm, 2)
        spans = np.append(np.diff(self.T), np.diff(self.T).mean())
        order = np.argsort(self.bpms)
        cum = np.cumsum(spans[order])
        return round(float(np.asarray(self.bpms)[order][np.searchsorted(cum, cum[-1] / 2)]), 2)

    def beat_at(self, t: float) -> float:
        if t >= self.T[-1]:
            return float(self.B[-1] + (t - self.T[-1]) * self.last_bpm / 60.0)
        if t < self.T[0]:
            return float(self.B[0] + (t - self.T[0]) * self.bpms[0] / 60.0)
        return float(np.interp(t, self.T, self.B))

    def time_at(self, beat: float) -> float:
        if beat >= self.B[-1]:
            return float(self.T[-1] + (beat - self.B[-1]) * 60.0 / self.last_bpm)
        if beat < self.B[0]:
            return float(self.T[0] + (beat - self.B[0]) * 60.0 / self.bpms[0])
        return float(np.interp(beat, self.B, self.T))

    def shifted(self, dt: float) -> "TempoMap":
        return TempoMap(self.T + dt, self.B, self.last_bpm)


CHANGE_COST = 0.8  # score a tempo change must earn before it is believed (a window scores 0-1.75)
CHANGE_SLOPE = 12.0  # ...plus this much per unit of ln(bpm ratio), so gradual tempo drift is cheap, jumps costly
OCTAVE_BONUS = 0.9
MIN_SEGMENT_S = 6.0
WINDOW_S, HOP_S = 10.0, 2.0


def _refine(t: np.ndarray, bpm: float, step_beats: float, span: float = 2.0) -> tuple[float, float]:
    def score(b: float) -> float:
        beat = 60.0 / b
        return sum(w * _resultant(t, beat * m)[0] for w, m in ((1.0, 1.0), (0.5, 0.5), (0.25, 0.25)))

    fine = np.arange(bpm - span, bpm + span + 1e-9, 0.05)
    best = float(max(fine, key=score))
    return best, _resultant(t, 60.0 / best * step_beats)[1]


def estimate_tempo_map(notes: list[Note], step_beats: float = 0.25, lo: float = 55, hi: float = 140) -> TempoMap:
    """Tempo changes included: slide a window over the onsets, score every candidate tempo in each, and let a
    Viterbi pass pick the best path where each change costs something. A piece that never changes tempo comes back
    exactly as `estimate_tempo` would give it."""
    t = onset_times(notes)
    bpm0, phase0 = estimate_tempo(notes, lo, hi, step_beats)
    if len(t) < 16 or t[-1] - t[0] < 2 * MIN_SEGMENT_S + WINDOW_S:
        return TempoMap.constant(bpm0, phase0)

    cands = np.arange(lo, hi + 1e-9, 0.5)
    periods = 60.0 / cands
    centers = np.arange(t[0], t[-1] + 1e-9, HOP_S)
    S = np.zeros((len(centers), len(cands)))
    for i, c in enumerate(centers):
        w = t[(t >= c - WINDOW_S / 2) & (t < c + WINDOW_S / 2)]
        if len(w) < 6:
            continue
        for wt, m in ((1.0, 1.0), (0.5, 0.5), (0.25, 0.25)):
            S[i] += wt * np.abs(np.exp(2j * np.pi * w[:, None] / (periods * m)[None, :]).mean(axis=0))
    S += OCTAVE_BONUS * (cands <= 120)  # a tempo and its double fit the onsets alike; prefer the slower reading
    trans = CHANGE_COST * (1 - np.eye(len(cands))) + CHANGE_SLOPE * np.abs(np.log(cands[None, :] / cands[:, None]))
    acc = S[0].copy()
    back = np.zeros((len(centers), len(cands)), int)
    for i in range(1, len(centers)):
        tot = acc[:, None] - trans
        back[i] = tot.argmax(axis=0)
        acc = tot.max(axis=0) + S[i]
    path = np.zeros(len(centers), int)
    path[-1] = int(acc.argmax())
    for i in range(len(centers) - 1, 0, -1):
        path[i - 1] = back[i, path[i]]

    # runs of equal tempo -> segments [start, end) in seconds; short ones are folded into a neighbour
    segs = []  # [start_time, bpm]
    for i, k in enumerate(path):
        if not segs or abs(cands[k] - segs[-1][1]) > 1e-9:
            segs.append([t[0] if i == 0 else (centers[i - 1] + centers[i]) / 2, float(cands[k])])
    ends = [s[0] for s in segs[1:]] + [t[-1] + 1e-6]
    keep = []
    for (st, b), en in zip(segs, ends):
        if keep and en - st < MIN_SEGMENT_S:
            continue
        keep.append([st, b, en])
    for a, b in zip(keep, keep[1:]):
        a[2] = b[0]
    keep[-1][2] = t[-1] + 1e-6
    if len(keep) == 1:
        return TempoMap.constant(bpm0, phase0)

    fits = []
    for st, b, en in keep:
        seg_t = t[(t >= st) & (t < en)]
        fits.append(_refine(seg_t, b, step_beats) if len(seg_t) >= 6 else (b, _resultant(seg_t, 60.0 / b * step_beats)[1] if len(seg_t) else 0.0))
    # Anchors: where one tempo hands over to the next, on the new segment's own beat lattice. The elapsed beats
    # come from the previous tempo. (The exact change point can't be found any better than the window hop
    # allows: tempo ratios like 11:8 put both beat lattices on the same positions.)
    T, B = [], []
    for i, ((st, _, _), (b, ph)) in enumerate(zip(keep, fits)):
        ss = 60.0 / b * step_beats
        if i == 0:
            T.append(ph)
            B.append(0.0)
            continue
        # tempo changes happen on a beat: prefer an anchor within a beat of the boundary that is a whole number
        # of beats after the previous one
        k0 = round((st - ph) / ss)
        reach = int(round(1.0 / step_beats))
        best = None
        for k in range(k0 - reach, k0 + reach + 1):
            elapsed = (ph + k * ss - T[-1]) * fits[i - 1][0] / 60.0
            cost = abs(elapsed - round(elapsed)) + 0.05 * abs(k - k0) * step_beats
            if best is None or cost < best[0]:
                best = (cost, k, elapsed)
        _, k, elapsed = best
        t_anchor = ph + k * ss
        beats = round(elapsed) if abs(elapsed - round(elapsed)) < 0.1 else round(elapsed / step_beats) * step_beats
        T.append(t_anchor)
        B.append(B[-1] + beats)
    # drop anchors that ended up out of order (a very short segment collapsed onto its neighbour)
    pairs = [(a, b) for a, b in zip(T, B)]
    clean = [pairs[0]]
    for a, b in pairs[1:]:
        if a > clean[-1][0] + 1e-6 and b > clean[-1][1]:
            clean.append((a, b))
    return TempoMap([a for a, _ in clean], [b for _, b in clean], fits[-1][0])


def quantize_map(notes: list[Note], tm: TempoMap, grid: str) -> tuple[list[Note], TempoMap]:
    """Snap notes to the grid in beats. Returns the notes (seconds, first anchor = time 0) and the shifted map."""
    step = GRIDS[grid]
    t0 = float(tm.T[0])
    out: list[Note] = []
    for n in notes:
        a = max(0, round(tm.beat_at(n.start) / step))
        b = max(round(tm.beat_at(n.end) / step), a + 1)
        out.append(Note(n.pitch, tm.time_at(a * step) - t0, tm.time_at(b * step) - t0, n.hand))
    return _fix_overlaps(out), tm.shifted(-t0)
