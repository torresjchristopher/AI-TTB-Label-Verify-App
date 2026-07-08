from labelscan.matching import text_check
from labelscan.models import OCRLine


def test_case_and_punctuation_match():
    lines = [OCRLine("STONE’S THROW", 0.97)]
    result = text_check("brand_name", "Stone's Throw", lines)
    assert result.status == "pass"


def test_unrelated_text_fails():
    lines = [OCRLine("OTHER BRAND", 0.99)]
    result = text_check("brand_name", "Stone's Throw", lines)
    assert result.status == "fail"
