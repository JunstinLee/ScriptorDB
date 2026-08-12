from __future__ import annotations

import json

from crawl4ai import JsonCssExtractionStrategy

from core.logging_setup import get_logger

logger = get_logger("crawl.structured")


def extract_rows(html: str, schema: dict | None) -> list | None:
    """Run JsonCssExtractionStrategy against already-fetched HTML.

    Returns the raw extracted row list (for cross-page merging), or None on
    failure.
    """
    if not isinstance(html, str) or not html or not schema or not isinstance(schema, dict):
        return None
    try:
        strategy = JsonCssExtractionStrategy(schema)
        return strategy.extract("", html)
    except Exception as e:
        logger.warning("schema extraction failed: %s", e)
        return None


def extract_with_schema(html: str, schema: dict | None) -> str | None:
    """Run JsonCssExtractionStrategy directly against already-fetched HTML.

    Returns the extracted rows as a JSON string, or None on failure.
    """
    rows = extract_rows(html, schema)
    if not rows:
        return None
    try:
        return json.dumps(rows, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning("schema extraction serialization failed: %s", e)
        return None


__all__ = ["extract_with_schema", "extract_rows"]
