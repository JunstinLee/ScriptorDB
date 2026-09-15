from __future__ import annotations

import asyncio
import traceback
from pathlib import Path

from pypdf import PdfReader

from core.logging_setup import get_logger
from schemas.pdf_models import PdfExtractResult

logger = get_logger("pdf")

MAX_TEXT_LENGTH = 50000
_TRUNCATION_MARKER = "\n\n[Content truncated — exceeded 50K characters]"


def _extract_metadata(reader: PdfReader) -> dict:
    meta = getattr(reader, "metadata", None)
    out: dict = {}
    if meta:
        try:
            items = dict(meta).items()
        except (TypeError, ValueError):
            items = ()
        for key, value in items:
            name = str(key).lstrip("/").lower()
            out[name] = "" if value is None else str(value)
    out["pages"] = len(reader.pages)
    return out


def _read_pdf(file_path: Path, max_chars: int) -> PdfExtractResult:
    reader = PdfReader(str(file_path))
    if reader.is_encrypted:
        reader.decrypt("")

    text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)

    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars] + _TRUNCATION_MARKER
        truncated = True

    return PdfExtractResult(
        path=str(file_path),
        text=text,
        metadata=_extract_metadata(reader),
        truncated=truncated,
    )


async def extract_pdf(path: str, max_chars: int = MAX_TEXT_LENGTH) -> PdfExtractResult:
    file_path = Path(path).resolve()
    if not file_path.is_file():
        return PdfExtractResult(path=str(path), error=f"File not found: {path}")

    try:
        return await asyncio.to_thread(_read_pdf, file_path, max_chars)
    except Exception as e:
        logger.error("Unexpected PDF extract error for %s: %s\n%s", path, e, traceback.format_exc())
        return PdfExtractResult(path=str(path), error=str(e))


__all__ = ["MAX_TEXT_LENGTH", "extract_pdf"]
