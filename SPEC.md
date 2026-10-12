# video2midi — Project Specification

Convert a YouTube video of a Synthesia-style piano tutorial (falling notes over a keyboard) into a MIDI file with left- and right-hand parts on separate tracks.

## Decisions

| Area | Decision |
|---|---|
| Form | Local web app (runs on the user's machine) |
| Backend | Python, FastAPI; yt-dlp, OpenCV, NumPy, mido |
| Frontend | React + Vite (TypeScript) |
| Input | YouTube URL (server downloads via yt-dlp) |
| Video support | Standard falling-note view, plus cropped/partial keyboards, intro/outro and watermark overlays |
| Hand split | By note color (two dominant falling-note colors); fallback to pitch split at a configurable key (default middle C / MIDI 60) if only one color is found |
| Output | One Type 1 MIDI file, two tracks: "Right Hand", "Left Hand" |
| Timing | Detect tempo and quantize (quantization adjustable / can be turned off) |
| UI extras | Progress indicator, calibration preview, piano-roll preview with audio playback, adjustable settings |

## Pipeline

1. **Download** — yt-dlp fetches the best video-only stream ≤1080p to a temp dir. Progress is reported.
2. **Calibrate** — sample frames to find:
   - the keyboard region and key range (auto-detect white/black key pattern; handle partial keyboards by mapping visible keys to MIDI pitches, with a manual start-key override),
   - the *hit line* (top edge of the keyboard, where notes land),
   - the two hand colors (k-means over saturated pixels in the falling-note area).
   - Output: a preview image with overlays (keyboard box, hit line, per-key columns, detected colors) shown for user confirmation/correction before full processing.
3. **Extract** — for each frame, sample a thin strip just above the hit line per key column; a key is "on" if the strip color matches a hand color. Track on/off per key, per hand, with debouncing to remove flicker. Frame time → seconds (using video FPS). Overlay/intro/outro frames without a keyboard are skipped.
4. **Notes** — merge on/off runs into notes (pitch, start, end, hand). Drop notes shorter than a minimum duration; merge tiny gaps (re-articulation threshold configurable). Fixed velocity (default 80, configurable).
5. **Tempo & quantize** — estimate BPM from onset intervals (autocorrelation / inter-onset histogram), snap onsets and durations to a grid (default 1/16, options 1/8, 1/32, off). Write tempo to the MIDI tempo map. If quantization is off, write at 120 BPM with exact times.
6. **Export** — mido writes Type 1 MIDI: Track 0 tempo/meta, Track 1 Right Hand, Track 2 Left Hand.

## Web app

- **Backend API (FastAPI)**
  - `POST /jobs` `{url, settings}` → job id
  - `GET /jobs/{id}` → status, stage, progress %, errors
  - `GET /jobs/{id}/events` → SSE progress stream
  - `GET /jobs/{id}/calibration` → preview image + detected params (editable)
  - `POST /jobs/{id}/process` `{calibration overrides, settings}` → run extraction
  - `GET /jobs/{id}/notes` → JSON notes for piano roll
  - `GET /jobs/{id}/midi` → download `.mid`
  - Jobs run in a background worker; state kept on disk in a temp workspace; cleaned up on request/expiry.
- **Frontend (React + Vite)**
  1. URL input + settings panel
  2. Progress bar with stage labels (download → calibrate)
  3. Calibration preview with editable keyboard box, hit line, first key, hand colors → Confirm
  4. Progress bar (extract → quantize → export)
  5. Piano-roll preview (right hand / left hand colored), in-browser audio playback (Web Audio / Tone.js piano sampler), download button
- **Adjustable settings**: quantize grid / off, tempo override, hand color overrides, fallback split pitch, crop region, start/end time, minimum note length, velocity.

## Repository layout (planned)

```
backend/
  app/ main.py jobs.py download.py calibrate.py extract.py notes.py tempo.py midi_export.py
  tests/
frontend/
  src/ (components: UrlForm, Progress, CalibrationView, PianoRoll, Player, SettingsPanel)
README.md
SPEC.md
```

## Testing

- Unit tests with synthetic frames (generated falling-note video with known ground-truth MIDI) → compare extracted notes (pitch/onset/duration tolerance).
- Tempo/quantize tests on known onset sets.
- Backend API tests with FastAPI TestClient; frontend smoke tests.

## Defaults / assumptions (change if wrong)

- Fixed note velocity; no pedal, dynamics or fingering extraction.
- Single piano, one hand color per hand; no chord-voicing recovery beyond what is visible.
- Personal/local use; no auth, no deployment, no multi-user queue.
- Requires Python 3.11+, Node 20+, and ffmpeg on the PATH.

## Open questions

1. Any sample videos to use as test fixtures (Synthesia style / channels)?
2. Is an optional pitch-based hand split override per-note-range wanted in v1, or only the fallback single split?
3. Should the app also accept an uploaded video file if YouTube downloads are blocked?

## Milestones

1. Backend core: download, calibrate, extract, export CLI-testable with synthetic video.
2. Tempo detection + quantization.
3. FastAPI job API with progress.
4. React UI: URL → progress → calibration → results.
5. Piano roll + audio playback, polish, docs.
