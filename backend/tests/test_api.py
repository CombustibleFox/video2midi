import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.jobs import JobManager
from .synth import render_video


def wait(client, jid, want, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/jobs/{jid}").json()
        if s["status"] in want or s["status"] == "error":
            return s
        time.sleep(0.2)
    raise TimeoutError


def test_upload_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "manager", JobManager(tmp_path / "jobs"))
    video = tmp_path / "v.avi"
    render_video(video, [(60 + i, i * 0.5, i * 0.5 + 0.4, "R") for i in range(5)] +
                 [(40 + i, i * 0.5, i * 0.5 + 0.4, "L") for i in range(5)])
    c = TestClient(main.app)
    with open(video, "rb") as f:
        r = c.post("/jobs", files={"file": ("v.avi", f, "video/x-msvideo")}, data={"settings": '{"quantize":"off"}'})
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    assert wait(c, jid, {"awaiting_confirmation"})["status"] == "awaiting_confirmation"
    cal = c.get(f"/jobs/{jid}/calibration").json()
    assert cal["calibration"]["n_white"] == 52
    assert c.get(cal["preview_url"]).headers["content-type"] == "image/png"
    assert c.get(f"/jobs/{jid}/midi").status_code == 409
    assert c.post(f"/jobs/{jid}/process", json={"settings": {"velocity": 100}}).status_code == 200
    assert wait(c, jid, {"done"})["status"] == "done"
    notes = c.get(f"/jobs/{jid}/notes").json()
    assert len(notes["notes"]) == 10
    assert c.get(f"/jobs/{jid}/midi").content[:4] == b"MThd"
    assert c.delete(f"/jobs/{jid}").status_code == 200
    assert c.get(f"/jobs/{jid}").status_code == 404


def test_rejects_bad_input(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "manager", JobManager(tmp_path / "jobs"))
    c = TestClient(main.app)
    assert c.post("/jobs", json={"url": "file:///etc/passwd"}).status_code == 422
    assert c.post("/jobs", json={"url": "https://x.y/z", "settings": {"quantize": "bad"}}).status_code == 422
    assert c.get("/jobs/../../etc").status_code in (404, 422)


def _make_job(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "manager", JobManager(tmp_path / "jobs"))
    video = tmp_path / "v.avi"
    render_video(video, [(60 + i, i * 0.5, i * 0.5 + 0.4, "R") for i in range(5)] +
                 [(40 + i, i * 0.5, i * 0.5 + 0.4, "L") for i in range(5)])
    c = TestClient(main.app)
    with open(video, "rb") as f:
        r = c.post("/jobs", files={"file": ("v.avi", f, "video/x-msvideo")}, data={"settings": '{"quantize":"off"}'})
    jid = r.json()["id"]
    wait(c, jid, {"awaiting_confirmation"})
    return c, jid


def _frames(data: bytes, tmp_path) -> int:
    import cv2

    p = tmp_path / "dl.mp4"
    p.write_bytes(data)
    cap = cv2.VideoCapture(str(p))
    n = 0
    while cap.read()[0]:
        n += 1
    return n


def test_clip_and_frame_download(tmp_path, monkeypatch):
    c, jid = _make_job(tmp_path, monkeypatch)
    r = c.get(f"/jobs/{jid}/clip", params={"start": 1.0, "duration": 2.0})
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"
    assert "attachment" in r.headers["content-disposition"]
    assert abs(_frames(r.content, tmp_path) - 60) <= 3  # 2 s at 30 fps

    r = c.get(f"/jobs/{jid}/frame", params={"t": 1.5})
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (720, 1280)  # full resolution of the source


def test_clip_works_without_ffmpeg(tmp_path, monkeypatch):
    import shutil

    c, jid = _make_job(tmp_path, monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    r = c.get(f"/jobs/{jid}/clip", params={"start": 0.5, "duration": 1.0})
    assert r.status_code == 200
    assert abs(_frames(r.content, tmp_path) - 30) <= 3


def test_clip_rejects_bad_ranges(tmp_path, monkeypatch):
    c, jid = _make_job(tmp_path, monkeypatch)
    assert c.get(f"/jobs/{jid}/clip", params={"start": -1}).status_code == 422
    assert c.get(f"/jobs/{jid}/clip", params={"duration": 500}).status_code == 422
    assert c.get(f"/jobs/{jid}/clip", params={"start": 9999}).status_code == 422
    assert c.get(f"/jobs/{jid}/frame", params={"t": 9999}).status_code == 422
    assert c.get("/jobs/" + "0" * 32 + "/clip").status_code == 404


def test_result_reports_video_offset(tmp_path, monkeypatch):
    """The piano roll starts at the first note; the offset says where that is in the video."""
    monkeypatch.setattr(main, "manager", JobManager(tmp_path / "jobs"))
    video = tmp_path / "v.avi"
    render_video(video, [(60 + i, i * 0.5, i * 0.5 + 0.4, "R") for i in range(4)] +
                 [(40 + i, i * 0.5, i * 0.5 + 0.4, "L") for i in range(4)], intro_s=1.0)
    c = TestClient(main.app)
    with open(video, "rb") as f:
        jid = c.post("/jobs", files={"file": ("v.avi", f, "video/x-msvideo")},
                     data={"settings": '{"quantize":"off"}'}).json()["id"]
    wait(c, jid, {"awaiting_confirmation"})
    c.post(f"/jobs/{jid}/process", json={})
    wait(c, jid, {"done"})
    res = c.get(f"/jobs/{jid}/notes").json()
    assert abs(res["video_offset"] - 1.0) < 0.15
    assert min(n["start"] for n in res["notes"]) < 0.05
