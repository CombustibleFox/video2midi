import shutil
import subprocess
from pathlib import Path
from typing import Callable

import cv2

Progress = Callable[[str, float, str], None]


def download_youtube(url: str, out_dir: Path, progress: Progress | None = None) -> Path:
    import yt_dlp

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            frac = d.get("downloaded_bytes", 0) / total if total else 0.0
            progress("downloading", min(frac, 1.0), "Downloading video")

    opts = {
        # prefer H.264 so OpenCV can decode it without a transcode
        "format": "bestvideo[height<=1080][vcodec^=avc1]/bestvideo[height<=1080]/best[height<=1080]",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = sorted(p for p in out_dir.glob("source.*") if p.suffix not in (".part", ".ytdl"))
    if not files:
        raise RuntimeError("download produced no file")
    return files[0]


def ensure_readable(path: Path) -> Path:
    """Return a path OpenCV can decode, transcoding to H.264 with ffmpeg if needed."""
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    if ok:
        return path
    if not shutil.which("ffmpeg"):
        raise RuntimeError("video cannot be decoded and ffmpeg is not installed")
    out = path.with_name("source_h264.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
        capture_output=True,
    )
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("ffmpeg transcode failed: " + r.stderr.decode(errors="ignore")[-300:])
    return out
