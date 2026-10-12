"""Command-line runner and diagnostics: python -m app.cli <url-or-file> [-o out.mid]"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from .calibrate import Calibration
from .download import download_youtube, ensure_readable, safe_filename
from .pipeline import run_calibration, run_extraction
from .settings import Settings


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a Synthesia-style video to a 2-track MIDI file")
    ap.add_argument("source", help="YouTube URL or video file")
    ap.add_argument("-o", "--output", help="output file (default: <video name>.mid in the current folder)")
    ap.add_argument("--workdir", help="keep intermediate files here (preview.png, notes.json, ...)")
    ap.add_argument("--cookies-from-browser", metavar="BROWSER", help="e.g. chrome, firefox")
    ap.add_argument("--quantize", default="1/32", help="1/4, 1/8, 1/16, 1/32 or off")
    ap.add_argument("--tempo", type=float, help="override detected BPM")
    ap.add_argument("--split", type=int, default=60, help="fallback hand split pitch")
    ap.add_argument("--start", type=float, default=0.0, help="start second")
    ap.add_argument("--end", type=float, help="end second")
    ap.add_argument("--first-midi", type=int, help="override MIDI pitch of the leftmost key")
    ap.add_argument("--workers", type=int, default=0, help="processes for frame analysis (0 = one per core)")
    ap.add_argument("--calibrate-only", action="store_true", help="only write preview.png and print detection")
    a = ap.parse_args()

    work = Path(a.workdir or tempfile.mkdtemp(prefix="video2midi-"))
    work.mkdir(parents=True, exist_ok=True)
    s = Settings.from_dict({"quantize": a.quantize, "tempo_override": a.tempo, "split_pitch": a.split,
                            "start_s": a.start, "end_s": a.end, "workers": a.workers})
    if a.source.startswith(("http://", "https://")):
        titles: list[str] = []
        video = download_youtube(a.source, work, lambda st, f, m: print(f"\r{m} {f:4.0%}", end=""),
                                 a.cookies_from_browser, titles.append)
        print()
        stem = safe_filename(titles[0] if titles else None)
    else:
        video = Path(a.source)
        stem = safe_filename(video.stem)
    if not a.output:
        a.output = f"{stem}.mid"
    video = ensure_readable(video)
    cal = run_calibration(video, work, s)
    if a.first_midi is not None:
        cal.first_midi = a.first_midi
    print("calibration:", json.dumps(cal.to_dict()))
    print(f"preview: {work / 'preview.png'}")
    if a.calibrate_only:
        return
    res = run_extraction(video, work, cal, s, lambda st, f, m: print(f"\r{st} {f:4.0%}", end=""))
    print()
    shutil.copy(work / "output.mid", a.output)
    notes = res["notes"]
    right = sum(n["hand"] == "R" for n in notes)
    print(f"wrote {a.output}: {len(notes)} notes ({right} right, {len(notes) - right} left), {res['bpm']} BPM" + (f" (tempo changes: {len(res['tempo_map']) - 1})" if len(res.get('tempo_map', [])) > 1 else ""))
    print(f"intermediate files in {work}")


if __name__ == "__main__":
    main()
