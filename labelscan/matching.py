from decimal import Decimal
from typing import Dict, Iterable, List, Sequence, Tuple

from rapidfuzz.fuzz import ratio, partial_ratio

from .models import Check, OCRLine
from .normalize import compact, normalize_text, parse_abv, parse_proof, parse_volume_ml

WARNING_HEADING = "GOVERNMENT WARNING:"
WARNING_BODY_ANCHORS = [
    "According to the Surgeon General",
    "women should not drink alcoholic beverages during pregnancy",
    "risk of birth defects",
    "impairs your ability to drive a car or operate machinery",
    "may cause health problems",
]


def windows(lines: Sequence[OCRLine], size: int = 4) -> Iterable[Tuple[str, float]]:
    texts = [line.text for line in lines]
    for start in range(len(texts)):
        for width in range(1, size + 1):
            subset = lines[start:start+width]
            if not subset:
                continue
            text = " ".join(line.text for line in subset)
            confidence = sum(line.confidence for line in subset) / len(subset)
            yield text, confidence


def best_match(expected: str, lines: Sequence[OCRLine]) -> Tuple[str, float, float]:
    if not expected.strip():
        return "", 0.0, 0.0
    expected_norm = normalize_text(expected)
    best_text, best_conf, best_score = "", 0.0, 0.0
    for text, confidence in windows(lines):
        text_norm = normalize_text(text)
        similarity = max(
            ratio(expected_norm, text_norm),
            partial_ratio(expected_norm, text_norm),
        ) / 100.0
        coverage = min(1.0, len(compact(text)) / max(1, len(compact(expected))))
        score = similarity * 0.78 + confidence * 0.17 + coverage * 0.05
        if score > best_score:
            best_text, best_conf, best_score = text, confidence, score
    return best_text, best_conf, best_score



def _document_tokens(lines: Sequence[OCRLine]):
    tokens = set()
    for line in lines:
        tokens.update(token for token in normalize_text(line.text).split() if token)
    return tokens


def _expected_tokens(value: str):
    # Keep meaningful alphanumeric field tokens. Very short punctuation-like
    # fragments are not useful for OCR evidence scoring.
    return [
        token for token in normalize_text(value).split()
        if len(compact(token)) >= 2
    ]


def token_coverage(expected: str, lines: Sequence[OCRLine]) -> float:
    expected_tokens = _expected_tokens(expected)
    if not expected_tokens:
        return 0.0

    document = _document_tokens(lines)
    matched = 0.0
    for expected_token in expected_tokens:
        if expected_token in document:
            matched += 1.0
            continue

        # Allow a small OCR error for longer words, but only as partial credit.
        best = 0.0
        for detected_token in document:
            similarity = ratio(expected_token, detected_token) / 100.0
            best = max(best, similarity)
        if len(expected_token) >= 6 and best >= 0.86:
            matched += 0.75

    return matched / len(expected_tokens)


def field_text_check(field: str, expected: str, lines: Sequence[OCRLine]) -> Check:
    """
    Field-aware positive-evidence matching.

    Extra OCR text is ignored. A field fails only when expected evidence is
    genuinely unsupported, not because unrelated descriptors are also present.
    """
    if not expected.strip():
        return Check(field, "not_supplied", reason="No expected value supplied.")

    detected, ocr_confidence, score = best_match(expected, lines)
    coverage = token_coverage(expected, lines)
    exact_present = compact(expected) in compact(" ".join(line.text for line in lines))

    if exact_present:
        return Check(
            field, "pass", expected, detected or expected,
            round(max(0.95, ocr_confidence), 3),
            "Expected text was found; unrelated label text was ignored."
        )

    # Brand names should be matched primarily as a single name, not against
    # surrounding product descriptors.
    if field == "brand_name":
        # Brand matching deliberately avoids partial-ratio passes: a missing or
        # extra character can represent a real brand mismatch. Exact normalized
        # matches pass above; near matches are routed to review.
        expected_norm = normalize_text(expected)
        brand_similarity = max(
            [ratio(expected_norm, normalize_text(line.text)) / 100.0 for line in lines]
            or [0.0]
        )
        if brand_similarity >= 0.97 and ocr_confidence >= 0.70:
            status, reason = "pass", "Strong normalized brand match."
        elif brand_similarity >= 0.82 or coverage >= 0.75:
            status, reason = "review", (
                "Probable brand match with a minor OCR difference; verify visually."
            )
        else:
            status, reason = "fail", "Expected brand is not supported by OCR evidence."
        return Check(
            field, status, expected, detected,
            round(max(brand_similarity, coverage, ocr_confidence), 3), reason
        )

    # Class/type fields are often split across multiple lines. Require positive
    # token coverage, but do not penalize variant descriptors such as JALAPEÑO.
    if field == "class_type":
        if coverage >= 0.99:
            status, reason = "pass", (
                "All expected class/type terms were found; extra descriptors were ignored."
            )
        elif coverage >= 0.66:
            status, reason = "review", (
                "Most expected class/type terms were found; verify the remaining term."
            )
        else:
            status, reason = "fail", (
                "Too few expected class/type terms were detected."
            )
        return Check(
            field, status, expected, detected,
            round(max(coverage, ocr_confidence), 3), reason
        )

    # Producer and address fields retain conservative fuzzy matching.
    if score >= 0.90 and ocr_confidence >= 0.70:
        status, reason = "pass", "Strong normalized OCR match."
    elif score >= 0.72 or coverage >= 0.75:
        status, reason = "review", "Probable match; verify visually."
    else:
        status, reason = "fail", "Expected value is not supported by reliable OCR evidence."
    return Check(
        field, status, expected, detected,
        round(max(score, coverage, ocr_confidence), 3), reason
    )


def text_check(field: str, expected: str, lines: Sequence[OCRLine]) -> Check:
    return field_text_check(field, expected, lines)


def _find_numeric_candidate(lines: Sequence[OCRLine], parser):
    candidates = []
    for text, confidence in windows(lines, 3):
        value = parser(text)
        if value is not None:
            candidates.append((value, text, confidence))
    return candidates


def abv_check(expected: str, lines: Sequence[OCRLine]) -> Check:
    if not expected.strip():
        return Check("alcohol_content", "not_supplied", reason="No expected value supplied.")
    expected_value = parse_abv(expected)
    if expected_value is None:
        return Check("alcohol_content", "review", expected=expected,
                     reason="Expected alcohol content could not be parsed.")
    candidates = _find_numeric_candidate(lines, parse_abv)
    if not candidates:
        return Check("alcohol_content", "fail", expected=expected,
                     reason="No ABV or proof evidence was detected.")
    value, text, confidence = min(candidates, key=lambda item: abs(item[0] - expected_value))
    difference = abs(value - expected_value)
    if difference <= Decimal("0.05"):
        status, reason = "pass", "Numeric alcohol content matches."
    else:
        status, reason = "fail", "Detected alcohol content differs."
    return Check("alcohol_content", status, str(expected_value), text,
                 round(float(confidence), 3), reason)


def volume_check(expected: str, lines: Sequence[OCRLine]) -> Check:
    if not expected.strip():
        return Check("net_contents", "not_supplied", reason="No expected value supplied.")
    expected_value = parse_volume_ml(expected)
    if expected_value is None:
        return Check("net_contents", "review", expected=expected,
                     reason="Expected net contents could not be parsed.")
    candidates = _find_numeric_candidate(lines, parse_volume_ml)
    if not candidates:
        return Check("net_contents", "fail", expected=expected,
                     reason="No net-contents evidence was detected.")
    value, text, confidence = min(candidates, key=lambda item: abs(item[0] - expected_value))
    status = "pass" if value == expected_value else "fail"
    reason = "Normalized volume matches." if status == "pass" else "Normalized volume differs."
    return Check("net_contents", status, "%s mL" % expected_value, text,
                 round(float(confidence), 3), reason)


def warning_check(lines: Sequence[OCRLine]) -> Check:
    full = " ".join(line.text for line in lines)
    full_normalized = normalize_text(full)
    exact_heading = WARNING_HEADING in full
    normalized_heading = "GOVERNMENT WARNING" in full_normalized

    # OCR often inserts line breaks or minor punctuation differences. Score each
    # required phrase fuzzily against the complete normalized OCR text.
    anchor_scores = [
        partial_ratio(normalize_text(anchor), full_normalized) / 100.0
        for anchor in WARNING_BODY_ANCHORS
    ]
    strong_anchors = sum(score >= 0.88 for score in anchor_scores)
    moderate_anchors = sum(score >= 0.72 for score in anchor_scores)
    mean_anchor_score = sum(anchor_scores) / len(anchor_scores)

    if exact_heading and strong_anchors >= 4:
        return Check(
            "government_warning", "pass",
            expected=WARNING_HEADING + " [standard warning body]",
            detected=WARNING_HEADING,
            confidence=round(max(0.90, mean_anchor_score), 3),
            reason="Exact capitalized heading and the required warning wording were detected. "
                   "Boldness still requires visual confirmation."
        )
    if exact_heading and moderate_anchors >= 4:
        return Check(
            "government_warning", "review",
            expected=WARNING_HEADING + " [standard warning body]",
            detected=WARNING_HEADING,
            confidence=round(mean_anchor_score, 3),
            reason="Exact heading was detected, but one or more body phrases require visual confirmation."
        )
    if normalized_heading and moderate_anchors >= 3:
        return Check(
            "government_warning", "review",
            expected=WARNING_HEADING + " [standard warning body]",
            detected="GOVERNMENT WARNING",
            confidence=round(mean_anchor_score, 3),
            reason="Warning appears present, but exact punctuation, capitalization, or wording "
                   "requires visual confirmation."
        )
    if moderate_anchors >= 2:
        return Check(
            "government_warning", "review",
            expected=WARNING_HEADING + " [standard warning body]",
            detected="Partial warning body",
            confidence=round(mean_anchor_score, 3),
            reason="Only partial warning evidence was detected."
        )
    return Check(
        "government_warning", "fail",
        expected=WARNING_HEADING + " [standard warning body]",
        detected="",
        confidence=round(mean_anchor_score, 3),
        reason="Required warning was not reliably detected in this image."
    )



def generic_compare(lines: Sequence[OCRLine]) -> List[Check]:
    """Identify common TTB components when no comparison profile is selected.

    Missing evidence is routed to review rather than fail because a submitted
    image may show only one panel of a multi-panel label.
    """
    abv_candidates = _find_numeric_candidate(lines, parse_abv)
    if abv_candidates:
        value, detected, confidence = max(abv_candidates, key=lambda item: item[2])
        abv = Check(
            "alcohol_content", "pass", detected=detected,
            confidence=round(float(confidence), 3),
            reason="Alcohol content or proof was detected."
        )
    else:
        abv = Check(
            "alcohol_content", "review", confidence=0.0,
            reason="Alcohol content was not detected in this image; check another label panel or review visually."
        )

    volume_candidates = _find_numeric_candidate(lines, parse_volume_ml)
    if volume_candidates:
        value, detected, confidence = max(volume_candidates, key=lambda item: item[2])
        volume = Check(
            "net_contents", "pass", detected=detected,
            confidence=round(float(confidence), 3),
            reason="Net contents were detected."
        )
    else:
        volume = Check(
            "net_contents", "review", confidence=0.0,
            reason="Net contents were not detected in this image; review visually."
        )

    warning = warning_check(lines)
    if warning.status == "fail":
        warning.status = "review"
        warning.reason = (
            "Government Warning was not detected in this image; it may appear on another label panel."
        )

    return [abv, volume, warning]


def compare(expected: Dict[str, str], lines: Sequence[OCRLine]) -> List[Check]:
    if not any(str(value).strip() for key, value in expected.items() if key not in {"filename", "application_id"}):
        return generic_compare(lines)

    checks = [
        text_check("brand_name", expected.get("brand_name", ""), lines),
        text_check("class_type", expected.get("class_type", ""), lines),
        abv_check(expected.get("alcohol_content", ""), lines),
        volume_check(expected.get("net_contents", ""), lines),
        text_check("producer_name", expected.get("producer_name", ""), lines),
        text_check("producer_address", expected.get("producer_address", ""), lines),
    ]
    imported = str(expected.get("imported", "")).strip().lower() in {"1", "true", "yes", "y"}
    if imported:
        checks.append(text_check("country_of_origin", expected.get("country_of_origin", ""), lines))
    else:
        checks.append(Check("country_of_origin", "not_applicable",
                            reason="Record is not marked as imported."))
    checks.append(warning_check(lines))
    return checks


def overall(checks: Sequence[Check]) -> str:
    supplied = [check for check in checks if check.status not in {"not_supplied", "not_applicable"}]
    if not supplied:
        return "ocr_only"
    if any(check.status == "fail" for check in supplied):
        return "fail"
    if any(check.status == "review" for check in supplied):
        return "review"
    return "pass"
