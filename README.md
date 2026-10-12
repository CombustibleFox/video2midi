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
