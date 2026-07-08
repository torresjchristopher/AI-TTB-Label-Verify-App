import csv
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .matching import compare, overall
from .models import ImageResult
from .ocr import quality, recognize

SUPPORTED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def load_manifest(path: Optional[str]) -> Dict[str, Dict[str, str]]:
    if not path:
        return {}
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ValueError("Manifest does not exist: %s" % manifest_path)
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "filename" not in reader.fieldnames:
            raise ValueError("Manifest must contain a filename column.")
        rows = {}
        for row in reader:
            filename = (row.get("filename") or "").strip()
            if filename:
                rows[filename.lower()] = {key: (value or "").strip() for key, value in row.items()}
        return rows


def list_images(input_path: str, recursive: bool, limit: Optional[int]) -> List[Path]:
    source = Path(input_path)
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED:
            raise ValueError("Unsupported image type: %s" % source.suffix)
        return [source]
    if not source.is_dir():
        raise ValueError("Input path does not exist: %s" % source)
    iterator = source.rglob("*") if recursive else source.iterdir()
    images = sorted(
        path for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )
    if limit is not None:
        images = images[:limit]
    if not images:
        raise ValueError("No supported images were found.")
    return images


def process_one(path: Path, expected: Dict[str, str], aggressive: bool) -> ImageResult:
    started = time.perf_counter()
    try:
        lines = recognize(str(path), aggressive=aggressive)
        mean_confidence, _ = quality(lines)
        text = "\n".join(line.text for line in lines)
        checks = compare(expected, lines)
        return ImageResult(
            filename=path.name,
            path=str(path.resolve()),
            application_id=expected.get("application_id", ""),
            status="completed",
            overall=overall(checks),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            ocr_confidence=round(mean_confidence, 3),
            extracted_text=text,
            checks=checks,
        )
    except Exception as exc:
        return ImageResult(
            filename=path.name,
            path=str(path.resolve()),
            application_id=expected.get("application_id", ""),
            status="error",
            overall="error",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            error="%s: %s" % (type(exc).__name__, exc),
        )


def write_outputs(results: List[ImageResult], output: str) -> Dict[str, object]:
    out = Path(output)
    text_dir = out / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        safe = Path(result.filename).stem.replace(" ", "_")
        (text_dir / (safe + ".txt")).write_text(
            result.extracted_text if result.extracted_text else result.error,
            encoding="utf-8",
        )

    json_path = out / "results.json"
    json_path.write_text(
        json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    csv_path = out / "results.csv"
    columns = [
        "filename", "application_id", "processing_status", "overall",
        "elapsed_ms", "ocr_confidence", "field", "check_status",
        "expected", "detected", "check_confidence", "reason", "error",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for result in results:
            if result.checks:
                for check in result.checks:
                    writer.writerow({
                        "filename": result.filename,
                        "application_id": result.application_id,
                        "processing_status": result.status,
                        "overall": result.overall,
                        "elapsed_ms": result.elapsed_ms,
                        "ocr_confidence": result.ocr_confidence,
                        "field": check.field,
                        "check_status": check.status,
                        "expected": check.expected,
                        "detected": check.detected,
                        "check_confidence": check.confidence,
                        "reason": check.reason,
                        "error": result.error,
                    })
            else:
                writer.writerow({
                    "filename": result.filename,
                    "application_id": result.application_id,
                    "processing_status": result.status,
                    "overall": result.overall,
                    "elapsed_ms": result.elapsed_ms,
                    "ocr_confidence": result.ocr_confidence,
                    "error": result.error,
                })

    completed_times = [result.elapsed_ms for result in results if result.status == "completed"]
    summary = {
        "total": len(results),
        "completed": sum(result.status == "completed" for result in results),
        "errors": sum(result.status == "error" for result in results),
        "pass": sum(result.overall == "pass" for result in results),
        "review": sum(result.overall == "review" for result in results),
        "fail": sum(result.overall == "fail" for result in results),
        "ocr_only": sum(result.overall == "ocr_only" for result in results),
        "median_ms": int(statistics.median(completed_times)) if completed_times else None,
        "p95_ms": (
            sorted(completed_times)[min(len(completed_times) - 1, max(0, int((len(completed_times) - 1) * 0.95 + 0.999999)))]
            if completed_times else None
        ),
        "results_csv": str(csv_path.resolve()),
        "results_json": str(json_path.resolve()),
        "text_directory": str(text_dir.resolve()),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def scan(
    input_path: str,
    manifest_path: Optional[str],
    output: str,
    workers: int,
    recursive: bool,
    limit: Optional[int],
    aggressive: bool,
) -> Dict[str, object]:
    images = list_images(input_path, recursive, limit)
    manifest = load_manifest(manifest_path)
    workers = max(1, min(workers, 4))

    results: List[ImageResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for path in images:
            expected = manifest.get(path.name.lower(), {})
            future = executor.submit(process_one, path, expected, aggressive)
            futures[future] = path

        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            print(
                "[%d/%d] %-8s %-8s %6d ms  %s"
                % (
                    completed, len(images), result.status, result.overall,
                    result.elapsed_ms, result.filename
                ),
                flush=True,
            )

    results.sort(key=lambda item: item.filename.lower())
    return write_outputs(results, output)
