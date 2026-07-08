import json
from pathlib import Path

from fastapi.testclient import TestClient

import web_app


def test_health():
    client = TestClient(web_app.app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["local_only"] is True


def test_fail_cannot_be_overridden(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "JOBS", tmp_path)
    job_id = "job1"
    output = tmp_path / job_id / "output"
    images = tmp_path / job_id / "images"
    output.mkdir(parents=True)
    images.mkdir(parents=True)
    (output / "results.json").write_text(json.dumps([{
        "filename": "label.jpg", "overall": "fail", "checks": []
    }]), encoding="utf-8")
    web_app._jobs[job_id] = {"status": "completed", "summary": {}}
    client = TestClient(web_app.app)
    response = client.post(f"/api/jobs/{job_id}/decisions", json={
        "filename": "label.jpg", "decision": "approved"
    })
    assert response.status_code == 409


def test_review_accepts_decision(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "JOBS", tmp_path)
    job_id = "job2"
    output = tmp_path / job_id / "output"
    images = tmp_path / job_id / "images"
    output.mkdir(parents=True)
    images.mkdir(parents=True)
    (output / "results.json").write_text(json.dumps([{
        "filename": "label.jpg", "overall": "review", "checks": []
    }]), encoding="utf-8")
    web_app._jobs[job_id] = {"status": "completed", "summary": {}}
    client = TestClient(web_app.app)
    response = client.post(f"/api/jobs/{job_id}/decisions", json={
        "filename": "label.jpg", "decision": "approved"
    })
    assert response.status_code == 200
    results = client.get(f"/api/jobs/{job_id}/results").json()
    assert results[0]["manual_decision"] == "approved"
