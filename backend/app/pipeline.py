"""Orchestrates calibration and note extraction for one video."""
import json
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .calibrate import Calibration, calibrate, render_preview
from .extract import extract_notes
from .midi_export import write_midi
from .notes import Note
from .settings import Settings
from .tempo import estimate_tempo, quantize

Progress = Callable[[str, float, str], None]


def _noop(*_a) -> None:
    pass


def run_calibration(video: Path, workdir: Path, settings: Settings, progress: Progress = _noop) -> Calibration:
    progress("calibrating", 0.0, "Analysing video")
    cal, med, frames = calibrate(str(video), hit_offset=settings.hit_offset)
    np.save(workdir / "median.npy", med)
    cv2.imwrite(str(workdir / "frame.png"), frames[len(frames) // 2])
    (workdir / "calibration.json").write_text(json.dumps(cal.to_dict()))
    write_preview(workdir, cal, settings)
    progress("calibrating", 1.0, "Calibration ready")
    return cal


def write_preview(workdir: Path, cal: Calibration, settings: Settings) -> Path:
    frame = cv2.imread(str(workdir / "frame.png"))
    out = workdir / "preview.png"
    cv2.imwrite(str(out), render_preview(frame, cal, settings.hit_offset))
    return out


def build_result(raw: list[Note], settings: Settings) -> tuple[list[Note], float, float]:
    """Apply trimming, tempo detection and quantization. Returns (notes, bpm, offset).

    `offset` is the video time (seconds) that the first note was moved to 0 from, so
    video time = note time + offset.
    """
    if not raw:
        return [], settings.tempo_override or 120.0, 0.0
    notes = [Note(n.pitch, n.start, n.end, n.hand) for n in raw]
    offset = 0.0
    if settings.trim_to_first_note:
        t0 = offset = min(n.start for n in notes)
        for n in notes:
            n.start -= t0
            n.end -= t0
    if settings.quantize == "off":
        return notes, 120.0, offset
    from .settings import GRIDS

    bpm, phase = estimate_tempo(notes, step_beats=GRIDS[settings.quantize])
    if settings.tempo_override:
        bpm = settings.tempo_override
        from .tempo import _resultant, onset_times

        t = onset_times(notes)
        phase = _resultant(t, 60.0 / bpm * GRIDS[settings.quantize])[1] if len(t) else 0.0
    return quantize(notes, bpm, phase, settings.quantize), bpm, offset


def run_extraction(video: Path, workdir: Path, cal: Calibration, settings: Settings,
                   progress: Progress = _noop) -> dict:
    ref_path = workdir / "median.npy"
    ref = np.load(ref_path) if ref_path.exists() else None
    progress("extracting", 0.0, "Reading notes from video")
    raw = extract_notes(str(video), cal, settings, ref, lambda f: progress("extracting", f, "Reading notes from video"))
    progress("exporting", 0.0, "Quantizing and writing MIDI")
    notes, bpm, offset = build_result(raw, settings)
    write_midi(notes, bpm, str(workdir / "output.mid"), settings.velocity)
    result = {"bpm": bpm, "video_offset": round(offset, 3), "notes": [n.to_dict() for n in notes]}
    (workdir / "notes.json").write_text(json.dumps(result))
    progress("done", 1.0, f"{len(notes)} notes")
    return result
