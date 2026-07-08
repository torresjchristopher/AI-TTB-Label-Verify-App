from labelscan.matching import text_check
from labelscan.models import OCRLine


def line(text, confidence=0.95):
    return OCRLine(text, confidence)


def test_extra_variant_descriptor_does_not_fail_class():
    lines = [
        line("Blanco"),
        line("Tequila 100%"),
        line("CASAMIGOS"),
        line("JALAPEÑO"),
        line("40% ALC. / VOL. (80 PROOF)"),
    ]
    result = text_check("class_type", "Tequila Blanco", lines)
    assert result.status == "pass"


def test_exact_brand_ignores_neighboring_text():
    lines = [
        line("PRODUCTOS CASAMIGOS DE AGAVE"),
        line("CASAMIGOS"),
        line("JALAPEÑO"),
    ]
    result = text_check("brand_name", "CASAMIGOS", lines)
    assert result.status == "pass"


def test_one_character_brand_error_is_review_not_fail():
    result = text_check("brand_name", "CASAMIGOS", [line("CASAMIGO")])
    assert result.status == "review"


def test_missing_expected_class_term_does_not_pass():
    result = text_check("class_type", "Tequila Blanco", [line("JALAPEÑO")])
    assert result.status == "fail"
