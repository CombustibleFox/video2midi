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


def _piece(segments, seed=1):
    """Notes on an eighth-note grid; segments = [(bpm, beats)]. Returns notes in seconds and the true onset seconds."""
    import numpy as np
    from app.notes import Note

    rng = np.random.default_rng(seed)
    notes, t = [], 0.0
    for bpm, beats in segments:
        for i in range(int(beats * 2)):
            if rng.random() < 0.85:
                notes.append(Note(int(rng.integers(40, 80)), t, t + 0.4 * 60 / bpm, "R" if i % 2 else "L"))
            t += 0.5 * 60 / bpm
    return notes


def test_tempo_changes_are_followed_and_written(tmp_path):
    from app.pipeline import build_result
    from app.settings import Settings
    import mido

    raw = _piece([(90, 60), (108, 70), (84, 60)])
    notes, tm, _ = build_result(raw, Settings(quantize="1/16"))
    bpms = [round(b) for b in tm.bpms]
    assert len(bpms) >= 3 and abs(bpms[0] - 90) <= 2 and abs(bpms[-1] - 84) <= 2 and any(abs(b - 108) <= 2 for b in bpms)
    # notes stay where they were played (seconds), within a sixteenth at the slowest tempo
    first = min(n.start for n in raw)
    played = sorted(n.start - first for n in raw)
    got = sorted(n.start for n in notes)
    assert len(played) == len(got) and max(abs(a - b) for a, b in zip(played, got)) < 0.08
    p = tmp_path / "t.mid"
    write_midi(notes, tm, str(p))
    mid = mido.MidiFile(str(p))
    tempos = [m for m in mid.tracks[0] if m.type == "set_tempo"]
    assert len(tempos) == len(bpms)
    assert abs(mid.length - (max(n.end for n in notes))) < 0.1  # playing the file takes as long as the notes say


def test_constant_tempo_stays_a_single_tempo():
    from app.pipeline import build_result
    from app.settings import Settings

    notes, tm, _ = build_result(_piece([(100, 150)], seed=3), Settings(quantize="1/16"))
    assert len(tm.bpms) == 1 and abs(tm.bpm - 100) < 1.5


def test_variable_tempo_can_be_switched_off():
    from app.pipeline import build_result
    from app.settings import Settings

    _, tm, _ = build_result(_piece([(90, 60), (108, 70)]), Settings(quantize="1/16", variable_tempo=False))
    assert len(tm.bpms) == 1


def test_exact_timing_keeps_note_times_and_follows_tempo_changes(tmp_path):
    from app.pipeline import build_result
    from app.settings import Settings
    import mido

    raw = _piece([(90, 60), (108, 70), (84, 60)])
    notes, tm, _ = build_result(raw, Settings(quantize="off"))
    first = min(n.start for n in raw)
    assert sorted(round(n.start, 6) for n in notes) == sorted(round(n.start - first, 6) for n in raw)  # untouched
    assert len(tm.bpms) >= 3
    p = tmp_path / "exact.mid"
    write_midi(notes, tm, str(p))
    mid = mido.MidiFile(str(p))
    ons, now = [], 0.0
    # play the file back: note-on times in seconds must equal the notes' own times
    for m in mid:
        now += m.time
        if m.type == "note_on" and m.velocity > 0:
            ons.append(round(now, 2))
    assert sorted(ons) == sorted(round(n.start, 2) for n in notes) or max(abs(a - b) for a, b in zip(sorted(ons), sorted(n.start for n in notes))) < 0.005
    _, tm1, _ = build_result(raw, Settings(quantize="off", variable_tempo=False))
    assert len(tm1.bpms) == 1


def test_safe_filename():
    from app.download import safe_filename

    assert safe_filename('A/B: C*?"<>|') == "A B C"
    assert safe_filename("  ..  ") == "output" and safe_filename(None) == "output"
    assert len(safe_filename("x" * 400)) <= 120
