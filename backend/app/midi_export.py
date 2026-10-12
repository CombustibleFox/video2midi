import mido

from .notes import Note
from .tempo import TempoMap

TICKS = 480


def write_midi(notes: list[Note], tempo: float | TempoMap, path: str, velocity: int = 80) -> None:
    """Type 1 MIDI: track 0 tempo, track 1 Right Hand, track 2 Left Hand. `tempo` is a BPM or a TempoMap."""
    tm = tempo if isinstance(tempo, TempoMap) else TempoMap.constant(tempo)
    mid = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("track_name", name="video2midi", time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    now = 0
    for beat, bpm in zip(tm.B, tm.bpms):
        tick = int(round(beat * TICKS))
        meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=tick - now))
        now = tick
    mid.tracks.append(meta)

    def ticks(sec: float) -> int:
        return int(round(tm.beat_at(sec) * TICKS))

    for name, hand in (("Right Hand", "R"), ("Left Hand", "L")):
        events = []
        for n in notes:
            if n.hand != hand:
                continue
            a = ticks(n.start)
            b = max(ticks(n.end), a + 1)
            events.append((a, 1, "note_on", n.pitch))
            events.append((b, 0, "note_off", n.pitch))  # offs sort before ons at the same tick
        events.sort()
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", program=0, channel=0, time=0))
        now = 0
        for tick, _, kind, pitch in events:
            track.append(mido.Message(kind, note=pitch, velocity=velocity if kind == "note_on" else 0,
                                      channel=0, time=tick - now))
            now = tick
        track.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(track)
    mid.save(path)
