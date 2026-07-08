from labelscan.matching import compare, overall
from labelscan.models import OCRLine


def line(text, confidence=0.95):
    return OCRLine(text, confidence)


def test_generic_missing_warning_is_review_not_fail():
    checks = compare({}, [line("40% ALC. / VOL. (80 PROOF)"), line("750 mL")])
    warning = next(check for check in checks if check.field == "government_warning")
    assert warning.status == "review"
    assert overall(checks) == "review"


def test_generic_detected_components_pass():
    lines = [
        line("40% ALC. / VOL. (80 PROOF)"), line("750 mL"),
        line("GOVERNMENT WARNING:"),
        line("According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects."),
        line("Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."),
    ]
    checks = compare({}, lines)
    assert all(check.status == "pass" for check in checks)
