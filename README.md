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

## Video quality

Detection works best on 720p or 1080p downloads. At 360p the keys are only a few pixels wide and the seam between two back-to-back notes of the same pitch can shrink to one pixel, so some repeated black-key notes get merged. Everything else (pitches, hands, timing) still works at 360p.
