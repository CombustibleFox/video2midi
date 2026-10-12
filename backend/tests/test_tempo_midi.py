import mido

from app.midi_export import write_midi
from app.notes import Note
from app.tempo import estimate_tempo, quantize


def test_tempo_and_quantize():
    beat = 60 / 132
    notes = [Note(60 + i % 5, i * beat / 2 + 0.01 * ((i * 7) % 3 - 1), i * beat / 2 + beat / 3, "R")
             for i in range(40)]
    bpm, phase = estimate_tempo(notes)
    assert abs(bpm - 132) < 1.5
    q = quantize(notes, bpm, phase, "1/8")
    steps = [n.start / (60 / bpm / 2) for n in q]
    assert all(abs(s - round(s)) < 1e-6 for s in steps)


def test_midi_tracks(tmp_path):
    notes = [Note(60, 0, 0.5, "R"), Note(60, 0.5, 1.0, "R"), Note(40, 0, 1.0, "L")]
    p = tmp_path / "a.mid"
    write_midi(notes, 120, str(p))
    mid = mido.MidiFile(str(p))
    assert mid.type == 1 and len(mid.tracks) == 3
    right = [m for m in mid.tracks[1] if m.type in ("note_on", "note_off")]
    assert [m.type for m in right] == ["note_on", "note_off", "note_on", "note_off"]
    assert mid.length > 0.99
