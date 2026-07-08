import threading
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from .models import OCRLine
from .normalize import compact

_thread_local = threading.local()


def get_engine():
    if not hasattr(_thread_local, "engine"):
        try:
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "RapidOCR is not installed. Run: python -m pip install "
                "--no-cache-dir -r requirements.txt"
            ) from exc
        _thread_local.engine = RapidOCR()
    return _thread_local.engine


def load_image(path: str) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        max_side = max(image.size)
        if max_side > 3200:
            scale = 3200.0 / max_side
            image = image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def clahe(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    light, a, b = cv2.split(lab)
    light = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(light)
    return cv2.cvtColor(cv2.merge((light, a, b)), cv2.COLOR_LAB2BGR)


def sharpen(image: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(image, (0, 0), 1.15)
    return cv2.addWeighted(image, 1.75, blur, -0.75, 0)


def threshold_variant(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 45, 45)
    out = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11
    )
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)


def upscale(image: np.ndarray, min_side: int = 1050) -> np.ndarray:
    h, w = image.shape[:2]
    short = min(h, w)
    if short >= min_side:
        return image
    scale = min(4.0, min_side / max(1, short))
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def rotate(image: np.ndarray, degrees: int) -> np.ndarray:
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def candidate_crops(image: np.ndarray) -> List[Tuple[str, np.ndarray]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 45, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 7))
    connected = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * 0.02
    max_area = h * w * 0.78
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = bw * bh
        aspect = bw / max(1, bh)
        if min_area <= area <= max_area and 0.35 <= aspect <= 5.0 and bw >= 70 and bh >= 40:
            boxes.append((area, x, y, bw, bh))
    boxes.sort(reverse=True)

    crops: List[Tuple[str, np.ndarray]] = []
    for index, (_, x, y, bw, bh) in enumerate(boxes[:4], start=1):
        padx, pady = int(bw * 0.12), int(bh * 0.18)
        crop = image[
            max(0, y - pady):min(h, y + bh + pady),
            max(0, x - padx):min(w, x + bw + padx),
        ]
        if crop.size:
            crops.append(("contour_%d" % index, crop))

    center_specs = [
        ("center_wide", 0.08, 0.22, 0.92, 0.90),
        ("center_label", 0.15, 0.30, 0.85, 0.82),
        ("lower_label", 0.10, 0.42, 0.90, 0.94),
    ]
    for name, x1, y1, x2, y2 in center_specs:
        crop = image[int(h*y1):int(h*y2), int(w*x1):int(w*x2)]
        if crop.size:
            crops.append((name, crop))
    return crops[:7]


def _coerce_lines(result: Any, source: str) -> List[OCRLine]:
    """Supports RapidOCR v2/v3 tuple and result-object shapes."""
    if result is None:
        return []

    # RapidOCR v3 result object commonly exposes txts, scores, boxes.
    txts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    boxes = getattr(result, "boxes", None)
    if txts is not None:
        scores = scores if scores is not None else [0.0] * len(txts)
        boxes = boxes if boxes is not None else [None] * len(txts)
        return [
            OCRLine(str(text), float(score), _box_to_list(box), source)
            for text, score, box in zip(txts, scores, boxes)
            if str(text).strip()
        ]

    if isinstance(result, dict):
        txts = result.get("txts") or result.get("texts") or []
        scores = result.get("scores") or result.get("confidences") or [0.0] * len(txts)
        boxes = result.get("boxes") or [None] * len(txts)
        return [
            OCRLine(str(text), float(score), _box_to_list(box), source)
            for text, score, box in zip(txts, scores, boxes)
            if str(text).strip()
        ]

    # RapidOCR v2 often returns (result_list, elapsed).
    payload = result
    if isinstance(result, tuple) and result:
        payload = result[0]

    lines = []
    if isinstance(payload, (list, tuple)):
        for item in payload:
            try:
                if len(item) >= 3:
                    box, text, score = item[0], item[1], item[2]
                elif len(item) == 2 and isinstance(item[1], (list, tuple)):
                    box = item[0]
                    text, score = item[1][0], item[1][1]
                else:
                    continue
                if str(text).strip():
                    lines.append(OCRLine(str(text), float(score), _box_to_list(box), source))
            except (TypeError, ValueError, IndexError):
                continue
    return lines


def _box_to_list(box: Any):
    if box is None:
        return None
    try:
        return [[float(point[0]), float(point[1])] for point in box]
    except Exception:
        return None


def run_once(image: np.ndarray, source: str) -> List[OCRLine]:
    result = get_engine()(image)
    return _coerce_lines(result, source)


def quality(lines: Sequence[OCRLine]) -> Tuple[float, int]:
    if not lines:
        return 0.0, 0
    return (
        sum(line.confidence for line in lines) / len(lines),
        sum(len(line.text.strip()) for line in lines),
    )


def merge(groups: Iterable[Sequence[OCRLine]]) -> List[OCRLine]:
    """
    Merge duplicate OCR lines while preserving approximate reading order.

    Full-image OCR is preferred for ordering. Crop-only discoveries are appended
    after the ordered full-image lines so field matching can still find them
    without scrambling multi-line statements such as the Government Warning.
    """
    best: Dict[str, OCRLine] = {}
    order: List[str] = []

    for group in groups:
        for line in group:
            key = compact(line.text)
            if len(key) < 2:
                continue
            if key not in best:
                best[key] = line
                order.append(key)
            elif line.confidence > best[key].confidence:
                best[key] = line

    return [best[key] for key in order]


def recognize(path: str, aggressive: bool = False) -> List[OCRLine]:
    image = load_image(path)
    groups: List[List[OCRLine]] = []

    base = clahe(image)
    first = run_once(base, "full_clahe")
    groups.append(first)
    confidence, characters = quality(first)

    retry = aggressive or confidence < 0.80 or characters < 100
    if retry:
        full = upscale(image, 900)
        for name, variant in [
            ("full_sharpen", sharpen(clahe(full))),
            ("full_threshold", threshold_variant(full)),
        ]:
            groups.append(run_once(variant, name))

        for crop_name, crop in candidate_crops(image):
            crop = upscale(crop, 1100)
            variants = [
                (crop_name + "_clahe", clahe(crop)),
                (crop_name + "_sharp", sharpen(clahe(crop))),
                (crop_name + "_threshold", threshold_variant(crop)),
            ]
            for source, variant in variants:
                groups.append(run_once(variant, source))

        neck = image[:max(1, int(image.shape[0] * 0.58)), :]
        neck = upscale(neck, 850)
        groups.append(run_once(rotate(neck, 90), "neck_rot90"))
        groups.append(run_once(rotate(neck, 270), "neck_rot270"))

    return merge(groups)
