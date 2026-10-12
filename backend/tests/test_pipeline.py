from pathlib import Path

import mido
import pytest

from app.calibrate import calibrate
from app.pipeline import run_calibration, run_extraction
from app.settings import Settings
from .synth import render_video

BPM = 100
BEAT = 60 / BPM
SIXTEENTH = BEAT / 4


def melody():
    """Right hand eighths/quarters, left hand half-note bass, one repeated pitch with a gap."""
    notes = []
    rh = [72, 74, 76, 77, 79, 79, 77, 76, 74, 72, 72, 76, 79, 76, 72, 67]
    t = 0.0
    for i, p in enumerate(rh):
        dur = BEAT / 2 if i % 4 else BEAT
        notes.append((p, t, t + dur - 0.1, "R"))
        t += dur
    lh = [48, 43, 48, 52, 45, 43]
    t = 0.0
    for p in lh:
        notes.append((p, t, t + 2 * BEAT - 0.1, "L"))
        t += 2 * BEAT
    return notes


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    d = tmp_path_factory.mktemp("v")
    path = d / "synth.avi"
    render_video(path, melody(), intro_s=1.0)
    return path, d


def test_calibration(video):
    path, _ = video
    cal, _, _ = calibrate(str(path))
    assert cal.n_white == 52
    assert cal.first_midi == 21
    assert abs(cal.top - 600) <= 2 and abs(cal.bottom - 719) <= 2
    assert len(cal.hues) == 2


def test_end_to_end(video):
    path, d = video
    s = Settings(quantize="1/16")
    cal = run_calibration(path, d, s)
    res = run_extraction(path, d, cal, s)
    truth = sorted(melody(), key=lambda n: (n[1], n[0]))
    got = res["notes"]
    assert len(got) == len(truth)
    assert abs(res["bpm"] - BPM) < 1.5
    t0 = truth[0][1]
    for (p, a, b, hand), g in zip(truth, sorted(got, key=lambda n: (n["start"], n["pitch"]))):
        assert g["pitch"] == p and g["hand"] == hand
        assert abs(g["start"] - (a - t0)) < 0.08

    mid = mido.MidiFile(str(d / "output.mid"))
    names = [t.name for t in mid.tracks]
    assert names[1:] == ["Right Hand", "Left Hand"]
    on = [sum(m.type == "note_on" for m in t) for t in mid.tracks[1:]]
    assert on == [16, 6]


def test_unquantized_and_split_fallback(video):
    path, d = video
    s = Settings(quantize="off")
    cal = run_calibration(path, d, s)
    cal.hues = cal.hues[:1]  # pretend only one color was found -> pitch split
    res = run_extraction(path, d, cal, s)
    assert res["bpm"] == 120.0
    hands = {n["pitch"]: n["hand"] for n in res["notes"]}
    assert all((h == "R") == (p >= 60) for p, h in hands.items())


def test_partial_keyboard(tmp_path):
    notes = [(60 + i % 7, i * 0.4, i * 0.4 + 0.3, "R") for i in range(8)] + \
            [(50 + i % 5, i * 0.8, i * 0.8 + 0.6, "L") for i in range(4)]
    path = tmp_path / "p.avi"
    render_video(path, notes, first_midi=48, n_white=22, intro_s=0.5)
    cal, _, _ = calibrate(str(path))
    assert cal.n_white == 22
    assert cal.first_midi % 12 == 0
    cal.first_midi = 48
    s = Settings(quantize="off")
    res = run_extraction(path, tmp_path, cal, s)
    assert sorted(n["pitch"] for n in res["notes"]) == sorted(p for p, *_ in notes)
