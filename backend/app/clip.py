"""Cut a short clip or grab a single frame from a job's source video, for sharing and debugging."""
import shutil
import subprocess
from pathlib import Path

import cv2

MAX_CLIP_S = 60.0


def video_duration(video: Path) -> float:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    return n / fps if fps else 0.0


def cut_clip(video: Path, start: float, duration: float, out: Path) -> Path:
    """Write [start, start + duration) of the video, without audio, to `out` (mp4)."""
    duration = min(duration, MAX_CLIP_S)
    if shutil.which("ffmpeg"):
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{duration:.3f}",
             "-an", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(out)],
            capture_output=True,
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
    return _cut_clip_opencv(video, start, duration, out)


def _cut_clip_opencv(video: Path, start: float, duration: float, out: Path) -> Path:
    """Fallback when ffmpeg is missing: re-encode with OpenCV (plays everywhere, larger files)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    first = int(round(start * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("could not create the clip (no ffmpeg and OpenCV cannot write mp4)")
    n = 0
    for _ in range(int(round(duration * fps))):
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        n += 1
    writer.release()
    cap.release()
    if n == 0:
        raise RuntimeError("no frames in that time range")
    return out


def grab_frame(video: Path, t: float, out: Path) -> Path:
    """Save the full-resolution frame at time t as a PNG."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps)))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("no frame at that time")
    cv2.imwrite(str(out), frame)
    return out
