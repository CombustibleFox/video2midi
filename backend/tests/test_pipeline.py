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
    assert 55 <= res["bpm"] <= 140  # exact timing still records the detected tempo
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


def test_back_to_back_repeats_are_split(tmp_path):
    """The key stays lit across touching same-pitch notes; only the seam between the bars shows the split."""
    notes = []
    t = 0.5
    for p, hand in ((60, "R"), (48, "L"), (64, "R")):
        for _ in range(3):  # three 0.3 s repeats with no gap
            notes.append((p, t, t + 0.3, hand))
            t += 0.3
        t += 0.6
    path = tmp_path / "rep.avi"
    render_video(path, notes, intro_s=0.0, speed=240.0, seam_px=4)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    got = sorted((n["pitch"], round(n["start"], 1)) for n in res["notes"])
    t0 = 0.5
    want = sorted((p, round(a - t0, 1)) for p, a, b, h in notes)
    assert got == want


def test_labels_on_bars_do_not_split_notes(tmp_path):
    """A white label across a narrow black-key bar looks like a gap in the bar color but is not a seam."""
    notes = [(61, 0.5, 1.4, "R"), (66, 2.0, 2.9, "R"), (48, 0.5, 1.4, "L"), (60, 2.0, 2.9, "L")]
    path = tmp_path / "lab.avi"
    render_video(path, notes, speed=240.0, seam_px=4, labels=True)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    assert sorted(n["pitch"] for n in res["notes"]) == [48, 60, 61, 66]


def test_parallel_matches_serial(tmp_path):
    """Frame analysis split across processes must give exactly the same result as one process."""
    import numpy as np

    from app.calibrate import calibrate
    from app.extract import MIN_PARALLEL_FRAMES, label_frames

    notes = [(48 + (i * 7) % 30, i * 0.45, i * 0.45 + 0.3, "R" if i % 2 else "L") for i in range(30)]
    path = tmp_path / "long.avi"
    render_video(path, notes, speed=240.0, seam_px=4)
    cal, med, _ = calibrate(str(path))
    assert cal.frame_count > MIN_PARALLEL_FRAMES
    serial = label_frames(str(path), cal, Settings(workers=1), med)
    parallel = label_frames(str(path), cal, Settings(workers=2), med)
    assert serial.labels.shape == parallel.labels.shape == (cal.frame_count, len(serial.pitches))
    assert np.array_equal(serial.labels, parallel.labels)
    assert np.array_equal(serial.bottoms, parallel.bottoms)
    assert serial.seams == parallel.seams


def test_dim_lit_black_keys_are_detected(tmp_path):
    """Lit black keys can be dim in real videos (brightness ~130-150); they must still count as pressed."""
    notes = [(61, 0.5, 1.2, "L"), (66, 1.5, 2.2, "R"), (58, 2.5, 3.2, "L"), (60, 0.5, 1.2, "R"), (64, 2.5, 3.2, "L")]
    path = tmp_path / "dim.avi"
    render_video(path, notes, speed=240.0, dim_black=True)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    assert sorted(n["pitch"] for n in res["notes"]) == [58, 60, 61, 64, 66]


def test_dark_line_seams_split_white_key_repeats(tmp_path):
    """At low resolution the seam between touching bars is a thin dark line, not a gap in the color."""
    notes = []
    t = 0.5
    for p, hand in ((60, "R"), (48, "L"), (64, "R")):
        for _ in range(3):
            notes.append((p, t, t + 0.3, hand))
            t += 0.3
        t += 0.6
    path = tmp_path / "dark.avi"
    render_video(path, notes, speed=240.0, dark_seam=True)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    got = sorted((n["pitch"], round(n["start"], 1)) for n in res["notes"])
    assert got == sorted((p, round(a - 0.5, 1)) for p, a, b, h in notes)


def test_thin_label_outline_is_not_a_seam_at_1080p(tmp_path):
    """The top edge of a label box is a one-row dark line across a narrow bar; a real seam is a thicker band."""
    notes = [(61, 0.5, 1.4, "R"), (66, 2.0, 2.9, "R"), (48, 0.5, 1.4, "L"), (60, 2.0, 2.9, "L"), (58, 3.2, 4.1, "L")]
    path = tmp_path / "outline1080.avi"
    render_video(path, notes, w=1920, h=1080, kb_h=180, speed=360.0, seam_px=6, labels=True, outline_rows=1)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    assert sorted(n["pitch"] for n in res["notes"]) == [48, 58, 60, 61, 66]


def test_thick_seam_still_splits_at_1080p(tmp_path):
    notes = []
    t = 0.5
    for p, hand in ((60, "R"), (48, "L"), (64, "R")):
        for _ in range(3):
            notes.append((p, t, t + 0.3, hand))
            t += 0.3
        t += 0.6
    path = tmp_path / "seam1080.avi"
    render_video(path, notes, w=1920, h=1080, kb_h=180, speed=360.0, seam_px=6)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    got = sorted((n["pitch"], round(n["start"], 1)) for n in res["notes"])
    assert got == sorted((p, round(a - 0.5, 1)) for p, a, b, h in notes)


def _gaps_between_repeats(res):
    by = {}
    for n in res["notes"]:
        by.setdefault(n["pitch"], []).append(n)
    out = []
    for lst in by.values():
        lst.sort(key=lambda n: n["start"])
        out += [b["start"] - a["end"] for a, b in zip(lst, lst[1:])]
    return out


def test_key_light_dropout_between_touching_repeats_is_closed(tmp_path):
    """Some videos switch the key light off ~2 frames between touching repeats. The notes still touch."""
    notes = []
    t = 0.5
    for p, hand in ((60, "R"), (48, "L"), (64, "R")):
        for _ in range(3):
            notes.append((p, t, t + 0.3, hand))
            t += 0.3
        t += 0.6
    path = tmp_path / "dropout.avi"
    render_video(path, notes, speed=240.0, seam_px=6, key_gap_s=0.07)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    gaps = _gaps_between_repeats(res)
    assert len(res["notes"]) == 9
    assert max(gaps) < 0.03, gaps  # touching, not 70 ms apart


def test_real_rest_between_repeats_is_kept(tmp_path):
    """A genuine rest has no seam (the bars are visibly apart), so it must not be closed."""
    notes = []
    t = 0.5
    for p, hand in ((60, "R"), (48, "L"), (64, "R")):
        for _ in range(3):
            notes.append((p, t, t + 0.3, hand))
            t += 0.55  # 0.25 s of silence between repeats
        t += 0.6
    path = tmp_path / "rests.avi"
    render_video(path, notes, speed=240.0, seam_px=6, key_gap_s=0.07)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    gaps = _gaps_between_repeats(res)
    assert len(res["notes"]) == 9
    assert min(g for g in gaps if g < 1.0) > 0.2, gaps


def test_hand_change_on_the_same_key_has_no_rest_and_no_late_start(tmp_path):
    """One hand's note followed straight away by the other hand's on the same key. The key light drops out
    in between, but the notes touch: no rest, and the second note starts when its bar arrives."""
    notes = [(40, 0.3, 0.9, "L"), (43, 1.0, 1.6, "L"), (72, 0.6, 1.2, "R"), (76, 1.4, 2.0, "R")]
    t = 2.6
    true_second_start = {}
    for p, first, second in ((60, "L", "R"), (62, "R", "L"), (64, "L", "R")):
        notes.append((p, t, t + 0.3, first))
        notes.append((p, t + 0.3, t + 0.6, second))
        true_second_start[p] = t + 0.3
        t += 1.0
    path = tmp_path / "handover.avi"
    render_video(path, notes, speed=240.0, seam_px=6, key_dark_s=0.05)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    t0 = min(n[1] for n in notes)  # the output starts at the first note
    for p, truth in true_second_start.items():
        pair = sorted((n for n in res["notes"] if n["pitch"] == p), key=lambda n: n["start"])
        assert len(pair) == 2 and pair[0]["hand"] != pair[1]["hand"], pair
        assert pair[1]["start"] - pair[0]["end"] < 0.03, pair  # no invented rest
        assert abs(pair[1]["start"] - (truth - t0)) < 0.04, (pair, truth - t0)  # not delayed


def test_dim_gray_keyboard_is_found(tmp_path):
    """Some videos draw the white keys as dim gray (~145) instead of white; the keyboard must still be found whole."""
    notes = [(60 + i, 0.5 + i * 0.5, 0.9 + i * 0.5, "R") for i in range(4)] + [(40 + i, 0.5 + i * 0.5, 1.1 + i * 0.5, "L") for i in range(4)]
    path = tmp_path / "dim_keys.avi"
    render_video(path, notes, white_level=145)
    cal, _, _ = calibrate(str(path))
    assert cal.n_white == 52 and cal.first_midi == 21
    assert abs(cal.top - 600) <= 3 and cal.bottom >= 716  # the whole 120-pixel keyboard, not a sliver
    s = Settings(quantize="off")
    res = run_extraction(path, tmp_path, run_calibration(path, tmp_path, s), s)
    assert sorted(n["pitch"] for n in res["notes"]) == sorted(p for p, *_ in notes)


def test_white_hand_and_differently_colored_keys(tmp_path):
    """One hand is white bars (keys light up white), the other orange bars whose keys light red; keyboard is dim gray."""
    notes = [(48, 0.5, 1.2, "L"), (52, 0.5, 1.2, "L"), (61, 1.5, 2.2, "L"), (67, 0.5, 1.2, "R"), (72, 1.5, 2.2, "R"), (66, 2.5, 3.2, "R"), (45, 2.5, 3.2, "L")]
    path = tmp_path / "white.avi"
    render_video(path, notes, speed=240.0, white_level=150, left_white=True, right_key=(40, 40, 230))
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    assert -1 in cal.hues and len(cal.hues) == 2
    res = run_extraction(path, tmp_path, cal, s)
    got = sorted((n["pitch"], n["hand"]) for n in res["notes"])
    assert got == sorted((p, h) for p, _, _, h in notes)


def test_glow_particles_and_a_rarely_used_hand(tmp_path):
    """Glossy videos: particle fountains, bloom and marbled bars; one hand plays only a few notes."""
    notes = []
    t = 0.5
    for p in (60, 64, 67, 64):
        for _ in range(3):  # touching repeats of the same key, split only by the seam between bars
            notes.append((p, t, t + 0.4, "R"))
            t += 0.4
        t += 0.6
    notes += [(48, 2.0, 2.6, "L"), (52, 6.0, 6.4, "L")]
    path = tmp_path / "fx.avi"
    render_video(path, notes, speed=300.0, seam_px=8, effects=True)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    assert len(cal.hues) == 2
    res = run_extraction(path, tmp_path, cal, s)
    t0 = min(a for _, a, _, _ in notes)
    got = sorted((n["pitch"], n["hand"], round(n["start"], 1)) for n in res["notes"])
    assert got == sorted((p, h, round(a - t0, 1)) for p, a, b, h in notes)


def test_key_glow_lingering_after_the_bar_does_not_lengthen_notes(tmp_path):
    """Sparks and glow keep a key lit for a while after its bar has ended; the bar's own length rules."""
    notes, t = [], 0.5
    for p in (60, 64, 67, 72, 62, 65):
        notes.append((p, t, t + 0.3, "R"))
        t += 0.7
    for p in (48, 52):
        notes.append((p, t, t + 0.3, "L"))
        t += 0.7
    path = tmp_path / "hold.avi"
    render_video(path, notes, speed=300.0, seam_px=0, key_hold_s=0.25, effects=True, fps=30)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    res = run_extraction(path, tmp_path, cal, s)
    durs = [n["end"] - n["start"] for n in res["notes"]]
    assert len(durs) == len(notes)
    assert max(durs) < 0.42, durs  # without the bar length these would be 0.55


def test_black_keys_are_found_where_they_really_sit(tmp_path):
    """Black keys lean off the line between two white keys; the calibration records by how much."""
    path = tmp_path / "k.avi"
    render_video(path, [(60, 0.5, 1.0, "R"), (40, 0.5, 1.0, "L")])
    cal = run_calibration(path, tmp_path, Settings(quantize="off"))
    assert cal.white_edges is not None and len(cal.white_edges) == cal.n_white + 1
    assert cal.black_centers is not None and len(cal.black_centers) == cal.n_white - 1


def test_uneven_keys_on_an_inset_keyboard_with_shaded_outer_keys(tmp_path):
    """Key lines are measured one by one, so keys of different widths, shaded outer keys and a keyboard that
    doesn't reach the frame edges are all handled."""
    notes = [(21, 0.5, 1.0, "L"), (24, 0.5, 1.0, "L"), (44, 1.2, 1.7, "L"), (61, 0.5, 1.0, "R"), (66, 1.2, 1.7, "R"),
             (70, 2.0, 2.5, "R"), (104, 0.5, 1.0, "R"), (108, 1.2, 1.7, "R"), (103, 2.0, 2.5, "R")]
    path = tmp_path / "uneven.avi"
    render_video(path, notes, speed=260.0, uneven_keys=True)
    s = Settings(quantize="off")
    cal = run_calibration(path, tmp_path, s)
    assert cal.n_white == 52 and cal.first_midi == 21
    assert cal.white_edges[0] < 45 and cal.white_edges[-1] > 1280 - 45
    res = run_extraction(path, tmp_path, cal, s)
    assert sorted(n["pitch"] for n in res["notes"]) == sorted(p for p, *_ in notes)
