import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Optional


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    value = value.upper()
    value = re.sub(r"[^A-Z0-9%./'():&+\- ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", normalize_text(value))


def parse_abv(value: str) -> Optional[Decimal]:
    value = value or ""
    patterns = [
        r"(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*(?:ALC|ALCOHOL).*?(?:VOL|VOLUME)",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if match:
            try:
                return Decimal(match.group(1))
            except InvalidOperation:
                return None
    proof = re.search(r"(\d{1,3}(?:\.\d+)?)\s*PROOF", value, re.I)
    if proof:
        try:
            return Decimal(proof.group(1)) / Decimal("2")
        except InvalidOperation:
            return None
    return None


def parse_proof(value: str) -> Optional[Decimal]:
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*PROOF", value or "", re.I)
    if not match:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


def parse_volume_ml(value: str) -> Optional[Decimal]:
    value = value or ""
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(ML|MILLILIT(?:ER|RE)S?|L|LIT(?:ER|RE)S?)\b",
        value,
        re.I,
    )
    if not match:
        return None
    try:
        number = Decimal(match.group(1))
    except InvalidOperation:
        return None
    unit = match.group(2).upper()
    if unit in {"L", "LITER", "LITRE", "LITERS", "LITRES"}:
        return number * Decimal("1000")
    return number
