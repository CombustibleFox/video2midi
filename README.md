# video2midi
Takes a youtube synthesia recording video and turns it into a functional midi file.

## Backend

```
cd backend
pip install -r requirements.txt   # needs ffmpeg on the PATH
uvicorn app.main:app --reload
pytest
```

See `SPEC.md` for the design. Set `VIDEO2MIDI_WORKDIR` to choose where job files are kept.

### Try it on a real video (CLI)

```
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt                       # also needs ffmpeg on the PATH
python -m app.cli "https://youtu.be/1BhX5hDaj5Y" -o out.mid --workdir ../run1
# if YouTube asks you to sign in:  add  --cookies-from-browser chrome
# or pass a downloaded file instead of a URL
```

Check `run1/preview.png` (detected keyboard, hit line, note colors) and the printed note counts.
`--calibrate-only` stops after the preview.

## Web app

```
# one-time
cd frontend && npm install && npm run build && cd ..
# run (serves the API and the built UI)
cd backend && uvicorn app.main:app --port 8000
# open http://localhost:8000
```

For frontend development run `npm run dev` in `frontend/` (http://localhost:5173, proxies API calls to :8000).
Flow: paste a YouTube URL or upload a file, check/adjust the detected keyboard and colors, convert, preview in the piano roll with playback, then download the `.mid`.

## Standalone executable

PyInstaller bundles Python, the backend and the built UI into one file (build it on each target OS):

```
cd frontend && npm install && npm run build && cd ../backend
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm video2midi.spec     # -> backend/dist/video2midi(.exe)
```

Run it: it starts the server and opens http://127.0.0.1:8000 in your browser. The GitHub Actions workflow
`Build executables` (Actions tab, Run workflow) builds Windows, macOS and Linux versions as downloadable artifacts.
ffmpeg is only needed if a downloaded video can't be decoded directly; install it and put it on the PATH.

## Performance

Frame analysis runs in parallel: the video is cut into chunks and a pool of worker processes (one per CPU core, up to 8) analyses them, then the results are stitched back together in order. The output is identical to the single-process result. Use `--workers N` on the CLI (`--workers 1` to disable) or the `workers` setting in the API. On a 4-core machine a 3.7 minute 1686x948 video takes about 40 seconds.

## Tempo changes

The tempo is estimated over a sliding window, so ritardandos and sections at a new tempo come out as tempo events in the MIDI file instead of one steady tempo. Notes keep the times they were played at; only the beat grid they snap to follows the tempo. Exact timing (quantize off) works with this too: notes keep their exact times and the file carries the tempo changes, so a DAW's beat grid lines up with the music. Turn it off with "Follow tempo changes" in the settings (or set a tempo override) to get a single tempo.

Limits: the exact bar where a change happens can't always be told from the notes alone, so after a change the beat grid can sit a fraction of a beat off the original score. Relative rhythm within each tempo section is kept. A tempo and its double fit the notes equally well, so the slower one is preferred (tempos are searched between 55 and 140 BPM).

## Video quality

Detection works best on 720p or 1080p downloads. At 360p the keys are only a few pixels wide and the seam between two back-to-back notes of the same pitch can shrink to one pixel, so some repeated black-key notes get merged. Everything else (pitches, hands, timing) still works at 360p.

Videos with glow, particle fountains and glossy semi-transparent bars work: notes are read from the lit keys, not the bars, and bar seams are only trusted when they are seen on many frames, so sparks and bloom near the keys don't split long notes. A second hand that plays very little is still found. Where sparks and glow keep a key lit after its bar has ended, the note ends where the bar's length says it does (only when the bar can be measured cleanly while it falls, and only to shorten).

## Sharing a problem spot

On the detection step and on the result page there is a **Save a clip or frame of the original video** box. Enter a video time (or, on the result page, move the piano-roll playhead and press **Use playhead**) and download a clip of up to 60 seconds (`.mp4`, no audio) or a full-resolution frame (`.png`). Clips use ffmpeg when it is installed and fall back to OpenCV otherwise. The piano roll starts at the first note, so the result page shows the offset to convert piano-roll time to video time.

## Themes and shortcuts

Pick a theme from the menu in the top-right corner; it is remembered. Themes: Midnight, Daylight, Sheet Music, Neon Keys, and three playful ones with their own scenery and a mascot that rides along the progress bar: Road Trip (a little purple car), Seaside Adventure (a friendly fish) and Fox Den (a fox in autumn woods). All artwork is original and drawn in SVG/CSS; animations stop if your system asks for reduced motion.

On the result page: **Space** plays/pauses, **←/→** skip 2 seconds, **Home** goes back to the start. The speed menu, hand buttons and zoom slider apply immediately. You can download both hands, only the right hand, or only the left hand.
