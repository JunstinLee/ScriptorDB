from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PdfExtractResult:
    path: str
    text: str = ""
    metadata: dict = field(default_factory=dict)
    truncated: bool = False
    error: str | None = None
