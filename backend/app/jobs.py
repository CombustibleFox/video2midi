import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .calibrate import Calibration
from .download import download_youtube, ensure_readable
from .pipeline import run_calibration, run_extraction, write_preview
from .settings import Settings

JOB_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class Job:
    id: str
    dir: Path
    settings: Settings
    url: str | None = None
    status: str = "queued"  # queued|downloading|calibrating|awaiting_confirmation|extracting|exporting|done|error
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    video: Path | None = None
    calibration: Calibration | None = None
    version: int = 0
    created: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, status: str | None = None, progress: float | None = None, message: str | None = None,
               error: str | None = None) -> None:
        with self.lock:
            if status is not None:
                self.status = status
            if progress is not None:
                self.progress = progress
            if message is not None:
                self.message = message
            if error is not None:
                self.error = error
            self.version += 1

    def snapshot(self) -> dict:
        return {"id": self.id, "status": self.status, "progress": self.progress, "message": self.message,
                "error": self.error, "version": self.version}


class JobManager:
    def __init__(self, base: Path | None = None):
        self.base = Path(base or os.environ.get("VIDEO2MIDI_WORKDIR") or tempfile.mkdtemp(prefix="video2midi-"))
        self.base.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}

    def create(self, settings: Settings, url: str | None = None) -> Job:
        jid = uuid.uuid4().hex
        d = self.base / jid
        d.mkdir()
        job = Job(id=jid, dir=d, settings=settings, url=url)
        self.jobs[jid] = job
        return job

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid) if JOB_ID.match(jid) else None

    def delete(self, jid: str) -> bool:
        job = self.get(jid)
        if not job:
            return False
        self.jobs.pop(jid, None)
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    # ---- background stages ----
    def _progress(self, job: Job):
        def cb(stage: str, frac: float, msg: str) -> None:
            job.update(status=stage, progress=frac, message=msg)
        return cb

    def start(self, job: Job, auto_process: bool = False) -> None:
        threading.Thread(target=self._prepare, args=(job, auto_process), daemon=True).start()

    def _prepare(self, job: Job, auto_process: bool) -> None:
        try:
            if job.url:
                job.update(status="downloading", progress=0.0, message="Downloading video")
                job.video = download_youtube(job.url, job.dir, self._progress(job))
            job.update(status="calibrating", progress=0.0, message="Preparing video")
            job.video = ensure_readable(job.video)
            job.calibration = run_calibration(job.video, job.dir, job.settings, self._progress(job))
            job.update(status="awaiting_confirmation", progress=1.0, message="Check the detected keyboard")
            if auto_process:
                self._extract(job)
        except Exception as e:  # surfaced to the UI
            job.update(status="error", error=str(e), message="Failed")

    def process(self, job: Job, calibration: Calibration, settings: Settings) -> None:
        job.calibration, job.settings = calibration, settings
        (job.dir / "calibration.json").write_text(json.dumps(calibration.to_dict()))
        job.update(status="extracting", progress=0.0, message="Reading notes from video")
        threading.Thread(target=self._extract, args=(job,), daemon=True).start()

    def _extract(self, job: Job) -> None:
        try:
            run_extraction(job.video, job.dir, job.calibration, job.settings, self._progress(job))
        except Exception as e:
            job.update(status="error", error=str(e), message="Failed")
