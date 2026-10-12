import asyncio
import json
import os
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from .calibrate import Calibration
from .clip import MAX_CLIP_S, cut_clip, grab_frame, video_duration
from .jobs import JobManager
from .midi_export import write_midi
from .tempo import TempoMap
from .notes import Note
from .pipeline import write_preview
from .settings import Settings

app = FastAPI(title="video2midi")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
manager = JobManager()

MAX_UPLOAD = 2 * 1024**3


def _job(jid: str):
    job = manager.get(jid)
    if not job:
        raise HTTPException(404, "job not found")
    return job


def _settings(d) -> Settings:
    try:
        return Settings.from_dict(d)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))


@app.post("/jobs")
async def create_job(request: Request):
    """JSON {url, settings, auto_process} or multipart (file, settings JSON string)."""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(422, "missing file")
        settings = _settings(json.loads(form.get("settings") or "{}"))
        job = manager.create(settings)
        dest = job.dir / ("source" + (Path(upload.filename or "").suffix.lower()[:8] or ".mp4"))
        size = 0
        with open(dest, "wb") as f:
            while chunk := await upload.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    manager.delete(job.id)
                    raise HTTPException(413, "file too large")
                f.write(chunk)
        job.video = dest
        auto = form.get("auto_process") == "true"
    else:
        body = await request.json()
        url = str(body.get("url", ""))
        if not url.startswith(("http://", "https://")):
            raise HTTPException(422, "url must be an http(s) link")
        job = manager.create(_settings(body.get("settings")), url=url)
        auto = bool(body.get("auto_process"))
    manager.start(job, auto)
    return job.snapshot()


@app.get("/jobs/{jid}")
def get_job(jid: str):
    return _job(jid).snapshot()


@app.delete("/jobs/{jid}")
def delete_job(jid: str):
    if not manager.delete(jid):
        raise HTTPException(404, "job not found")
    return {"ok": True}


@app.get("/jobs/{jid}/events")
async def events(jid: str, request: Request):
    job = _job(jid)

    async def gen():
        seen = -1
        while not await request.is_disconnected():
            if job.version != seen:
                seen = job.version
                yield f"data: {json.dumps(job.snapshot())}\n\n"
            else:
                yield ": keep-alive\n\n" if seen < 0 else ""
            await asyncio.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/jobs/{jid}/calibration")
def get_calibration(jid: str):
    job = _job(jid)
    if not job.calibration:
        raise HTTPException(409, "calibration not ready")
    return {"calibration": job.calibration.to_dict(), "settings": job.settings.__dict__,
            "preview_url": f"/jobs/{jid}/calibration/preview.png"}


@app.get("/jobs/{jid}/calibration/preview.png")
def preview(jid: str):
    job = _job(jid)
    p = job.dir / "preview.png"
    if not p.exists():
        raise HTTPException(409, "preview not ready")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/jobs/{jid}/calibration/preview")
async def update_preview(jid: str, request: Request):
    """Re-render the overlay for edited calibration values without processing."""
    job = _job(jid)
    if not job.calibration:
        raise HTTPException(409, "calibration not ready")
    body = await request.json()
    cal = Calibration.from_dict({**job.calibration.to_dict(), **(body.get("calibration") or {})})
    settings = _settings({**job.settings.__dict__, **(body.get("settings") or {})})
    path = write_preview(job.dir, cal, settings)
    return Response(path.read_bytes(), media_type="image/png")


@app.post("/jobs/{jid}/process")
async def process(jid: str, request: Request):
    job = _job(jid)
    if job.status not in ("awaiting_confirmation", "done", "error") or not job.calibration:
        raise HTTPException(409, f"job is {job.status}")
    body = await request.json() if await request.body() else {}
    try:
        cal = Calibration.from_dict({**job.calibration.to_dict(), **(body.get("calibration") or {})})
    except TypeError as e:
        raise HTTPException(422, str(e))
    settings = _settings({**job.settings.__dict__, **(body.get("settings") or {})})
    manager.process(job, cal, settings)
    return job.snapshot()


@app.get("/jobs/{jid}/clip")
def clip(jid: str, start: float = 0.0, duration: float = 25.0):
    """A short clip of the original video (no audio), handy for sharing a problem spot."""
    job = _job(jid)
    if not job.video or not job.video.exists():
        raise HTTPException(409, "video not ready")
    if start < 0 or not 1 <= duration <= MAX_CLIP_S:
        raise HTTPException(422, f"start must be >= 0 and duration between 1 and {int(MAX_CLIP_S)} seconds")
    if start >= video_duration(job.video):
        raise HTTPException(422, "start is past the end of the video")
    out = job.dir / f"clip_{start:.2f}_{duration:.2f}.mp4"
    if not out.exists():
        try:
            cut_clip(job.video, start, duration, out)
        except RuntimeError as e:
            raise HTTPException(500, str(e))
    return FileResponse(out, media_type="video/mp4", filename=f"clip_{int(start)}s.mp4")


@app.get("/jobs/{jid}/frame")
def frame(jid: str, t: float = 0.0):
    """One full-resolution frame of the original video as a PNG."""
    job = _job(jid)
    if not job.video or not job.video.exists():
        raise HTTPException(409, "video not ready")
    if t < 0:
        raise HTTPException(422, "t must be >= 0")
    out = job.dir / f"frame_{t:.2f}.png"
    if not out.exists():
        try:
            grab_frame(job.video, t, out)
        except RuntimeError as e:
            raise HTTPException(422, str(e))
    return FileResponse(out, media_type="image/png", filename=f"frame_{t:.1f}s.png")


@app.get("/jobs/{jid}/notes")
def notes(jid: str):
    job = _job(jid)
    p = job.dir / "notes.json"
    if job.status != "done" or not p.exists():
        raise HTTPException(409, "result not ready")
    return Response(p.read_bytes(), media_type="application/json")


@app.get("/jobs/{jid}/midi")
def midi(jid: str, hand: str = "both"):
    """The MIDI file; hand=R or hand=L gives a file with only that hand's notes."""
    job = _job(jid)
    p = job.dir / "output.mid"
    if job.status != "done" or not p.exists():
        raise HTTPException(409, "result not ready")
    if hand not in ("both", "R", "L"):
        raise HTTPException(422, "hand must be both, R or L")
    if hand == "both":
        return FileResponse(p, media_type="audio/midi", filename="output.mid")
    result = json.loads((job.dir / "notes.json").read_text())
    notes = [Note(**n) for n in result["notes"] if n["hand"] == hand]
    out = job.dir / f"output_{hand}.mid"
    write_midi(notes, TempoMap.from_list(result["tempo_map"]) if result.get("tempo_map") else result["bpm"], str(out), job.settings.velocity)
    return FileResponse(out, media_type="audio/midi", filename=f"output_{'right' if hand == 'R' else 'left'}_hand.mid")


# Serve the built frontend (npm run build in frontend/) from the same port.
import sys

if getattr(sys, "frozen", False):  # PyInstaller bundle
    _dist = Path(sys._MEIPASS) / "frontend_dist"
else:
    _dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
