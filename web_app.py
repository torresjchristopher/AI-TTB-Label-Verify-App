from __future__ import annotations

import csv
import json
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from labelscan.pipeline import scan

BASE = Path(__file__).resolve().parent
STATIC = BASE / "web" / "static"
JOBS = BASE / "runtime" / "jobs"
JOBS.mkdir(parents=True, exist_ok=True)

MAX_FILES = 250
MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
JOB_TTL_SECONDS = 6 * 60 * 60

app = FastAPI(title="TTB LabelVerify", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

_jobs: Dict[str, Dict[str, object]] = {}
_jobs_lock = threading.Lock()
_decision_lock = threading.Lock()


def _cleanup_old_jobs() -> None:
    now = time.time()
    for child in JOBS.iterdir():
        try:
            if child.is_dir() and now - child.stat().st_mtime > JOB_TTL_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            pass


def _set_job(job_id: str, **values: object) -> None:
    with _jobs_lock:
        _jobs.setdefault(job_id, {}).update(values)


def _get_job(job_id: str) -> Dict[str, object]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found or expired.")
        return dict(job)


def _job_path(job_id: str) -> Path:
    _get_job(job_id)
    path = JOBS / job_id
    if not path.is_dir():
        raise HTTPException(404, "Job files are unavailable.")
    return path


def _load_decisions(job_id: str) -> Dict[str, Dict[str, object]]:
    path = JOBS / job_id / "output" / "review-decisions.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {str(row["filename"]).lower(): row for row in rows}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _write_decisions(job_id: str, decisions: Dict[str, Dict[str, object]]) -> None:
    output = JOBS / job_id / "output"
    output.mkdir(parents=True, exist_ok=True)
    rows = sorted(decisions.values(), key=lambda row: str(row["filename"]).lower())
    (output / "review-decisions.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    with (output / "review-decisions.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["filename", "decision", "decided_at", "original_status"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _load_results(job_id: str) -> List[Dict[str, object]]:
    path = JOBS / job_id / "output" / "results.json"
    if not path.exists():
        raise HTTPException(404, "Results are unavailable.")
    results = json.loads(path.read_text(encoding="utf-8"))
    decisions = _load_decisions(job_id)
    for row in results:
        decision = decisions.get(str(row.get("filename", "")).lower())
        row["manual_decision"] = decision.get("decision") if decision else ""
        row["final_status"] = row["manual_decision"] or row.get("overall", "")
    return results


def _run_job(job_id: str, image_dir: Path, manifest: Optional[Path], output_dir: Path,
             workers: int, aggressive: bool) -> None:
    _set_job(job_id, status="running", started_at=time.time())
    try:
        summary = scan(
            input_path=str(image_dir),
            manifest_path=str(manifest) if manifest else None,
            output=str(output_dir),
            workers=workers,
            recursive=False,
            limit=None,
            aggressive=aggressive,
        )
        _write_decisions(job_id, {})
        _set_job(job_id, status="completed", summary=summary, finished_at=time.time())
    except Exception as exc:
        _set_job(job_id, status="error", error=f"{type(exc).__name__}: {exc}", finished_at=time.time())


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> Dict[str, object]:
    return {"status": "ok", "local_only": True, "max_files": MAX_FILES}


@app.post("/api/jobs")
async def create_job(
    files: List[UploadFile] = File(...),
    profile: str = Form(""),
    workers: int = Form(2),
    aggressive: bool = Form(False),
) -> Dict[str, str]:
    _cleanup_old_jobs()
    if not files:
        raise HTTPException(400, "Choose at least one image.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"A batch may contain at most {MAX_FILES} images.")
    workers = max(1, min(int(workers), 4))

    job_id = uuid.uuid4().hex
    job_dir = JOBS / job_id
    image_dir = job_dir / "images"
    output_dir = job_dir / "output"
    image_dir.mkdir(parents=True)

    saved_names: List[str] = []
    seen = set()
    try:
        for upload in files:
            name = Path(upload.filename or "").name
            suffix = Path(name).suffix.lower()
            if not name or suffix not in ALLOWED:
                raise HTTPException(400, f"Unsupported image: {name or '(unnamed)'}")
            if name.lower() in seen:
                raise HTTPException(400, f"Duplicate filename: {name}")
            seen.add(name.lower())
            data = await upload.read()
            if not data or len(data) > MAX_FILE_BYTES:
                raise HTTPException(400, f"Invalid or oversized image: {name}")
            (image_dir / name).write_bytes(data)
            saved_names.append(name)

        manifest_path: Optional[Path] = None
        if profile.strip():
            try:
                profile_data = json.loads(profile)
            except json.JSONDecodeError:
                raise HTTPException(400, "The selected label profile is invalid.")
            allowed_fields = [
                "application_id", "brand_name", "class_type", "alcohol_content",
                "net_contents", "producer_name", "producer_address",
                "country_of_origin", "imported",
            ]
            manifest_path = job_dir / "manifest.csv"
            with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["filename"] + allowed_fields)
                writer.writeheader()
                clean = {field: str(profile_data.get(field, "")).strip() for field in allowed_fields}
                for name in saved_names:
                    writer.writerow({"filename": name, **clean})

        _set_job(job_id, status="queued", total=len(files), created_at=time.time())
        thread = threading.Thread(
            target=_run_job,
            args=(job_id, image_dir, manifest_path, output_dir, workers, aggressive),
            daemon=True,
        )
        thread.start()
        return {"job_id": job_id}
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> Dict[str, object]:
    return _get_job(job_id)


@app.get("/api/jobs/{job_id}/results")
def job_results(job_id: str) -> object:
    job = _get_job(job_id)
    if job.get("status") != "completed":
        raise HTTPException(409, "Job is not complete.")
    return _load_results(job_id)


@app.get("/api/jobs/{job_id}/images/{filename}")
def job_image(job_id: str, filename: str) -> FileResponse:
    job_dir = _job_path(job_id)
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(400, "Invalid filename.")
    path = job_dir / "images" / safe_name
    if not path.is_file():
        raise HTTPException(404, "Image not found.")
    return FileResponse(path)


@app.post("/api/jobs/{job_id}/decisions")
def save_decision(job_id: str, payload: Dict[str, str] = Body(...)) -> Dict[str, object]:
    job = _get_job(job_id)
    if job.get("status") != "completed":
        raise HTTPException(409, "Job is not complete.")
    filename = Path(str(payload.get("filename", ""))).name
    decision = str(payload.get("decision", "")).lower()
    if decision not in {"approved", "denied"}:
        raise HTTPException(400, "Decision must be approved or denied.")

    results = _load_results(job_id)
    result = next((row for row in results if str(row.get("filename", "")).lower() == filename.lower()), None)
    if not result:
        raise HTTPException(404, "Image result not found.")
    if result.get("overall") not in {"review", "fail"}:
        raise HTTPException(
            409,
            "Only machine review or failure results accept a manual decision."
        )

    with _decision_lock:
        decisions = _load_decisions(job_id)
        decisions[filename.lower()] = {
            "filename": filename,
            "decision": decision,
            "decided_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original_status": str(result.get("overall", "")),
        }
        _write_decisions(job_id, decisions)
    return {"filename": filename, "decision": decision, "saved": True}


@app.get("/api/jobs/{job_id}/download/{name}")
def download(job_id: str, name: str) -> FileResponse:
    _get_job(job_id)
    allowed = {
        "results.csv", "results.json", "summary.json",
        "review-decisions.csv", "review-decisions.json",
    }
    if name not in allowed:
        raise HTTPException(404, "File not found.")
    path = JOBS / job_id / "output" / name
    if not path.exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(path, filename=name)
