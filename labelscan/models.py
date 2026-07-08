from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class OCRLine:
    text: str
    confidence: float
    box: Optional[List[List[float]]] = None
    source: str = "full"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Check:
    field: str
    status: str
    expected: str = ""
    detected: str = ""
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ImageResult:
    filename: str
    path: str
    application_id: str = ""
    status: str = "completed"
    overall: str = "ocr_only"
    elapsed_ms: int = 0
    ocr_confidence: float = 0.0
    extracted_text: str = ""
    checks: List[Check] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [check.to_dict() for check in self.checks]
        return data
