from __future__ import annotations

import traceback
from pathlib import Path

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.processors.pdf import PDFContentScrapingStrategy, PDFCrawlerStrategy

from logging_setup import get_logger
from schemas.pdf_models import PdfExtractResult

logger = get_logger("pdf")

MAX_TEXT_LENGTH = 50000
_TRUNCATION_MARKER = "\n\n[Content truncated — exceeded 50K characters]"


def _extract_raw_markdown(result: object) -> str:
    md = getattr(result, "markdown", None)
    if isinstance(md, str):
        return md
    if md is not None:
        raw = getattr(md, "raw_markdown", None)
        if isinstance(raw, str):
            return raw
    return ""


def _extract_metadata(result: object) -> dict:
    meta = getattr(result, "metadata", None)
    if isinstance(meta, dict):
        return dict(meta)
    return {}


async def extract_pdf(path: str, max_chars: int = MAX_TEXT_LENGTH) -> PdfExtractResult:
    file_path = Path(path).resolve()
    if not file_path.is_file():
        return PdfExtractResult(path=str(path), error=f"File not found: {path}")

    url = file_path.as_uri()
    try:
        async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
            config = CrawlerRunConfig(scraping_strategy=PDFContentScrapingStrategy())
            result = await crawler.arun(url=url, config=config)

        if not result:
            return PdfExtractResult(path=str(path), error="No response from PDF extractor")

        text = _extract_raw_markdown(result)
        if not text.strip() and not getattr(result, "success", False):
            error = getattr(result, "error_message", None) or "Failed to extract PDF text"
            return PdfExtractResult(path=str(path), error=error)

        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars] + _TRUNCATION_MARKER
            truncated = True

        return PdfExtractResult(
            path=str(path),
            text=text,
            metadata=_extract_metadata(result),
            truncated=truncated,
        )
    except Exception as e:
        logger.error("Unexpected PDF extract error for %s: %s\n%s", path, e, traceback.format_exc())
        return PdfExtractResult(path=str(path), error=str(e))


__all__ = ["MAX_TEXT_LENGTH", "extract_pdf"]
