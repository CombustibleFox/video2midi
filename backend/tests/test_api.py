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
