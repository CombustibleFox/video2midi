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
