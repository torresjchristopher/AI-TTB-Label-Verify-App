from decimal import Decimal
from labelscan.normalize import normalize_text, parse_abv, parse_volume_ml


def test_apostrophe_normalization():
    assert normalize_text("Stone’s Throw") == "STONE'S THROW"


def test_abv():
    assert parse_abv("45% Alc./Vol. (90 Proof)") == Decimal("45")
    assert parse_abv("90 Proof") == Decimal("45")


def test_volume():
    assert parse_volume_ml("0.75 L") == Decimal("750.00")
    assert parse_volume_ml("750 mL") == Decimal("750")
