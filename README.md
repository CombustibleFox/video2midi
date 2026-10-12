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
