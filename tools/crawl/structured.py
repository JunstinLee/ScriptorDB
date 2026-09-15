from __future__ import annotations

import json

from bs4 import BeautifulSoup

from core.logging_setup import get_logger

logger = get_logger("crawl.structured")


def _field_value(element, field: dict):
    selector = field.get("selector")
    node = element.select_one(selector) if selector else element
    if node is None:
        return field.get("default")

    field_type = (field.get("type") or "text").lower()
    if field_type == "text":
        return node.get_text(strip=True)
    if field_type == "attribute":
        return node.get(field.get("attribute") or "")
    if field_type == "html":
        return node.decode_contents()
    logger.warning("unknown schema field type %r — falling back to text", field_type)
    return node.get_text(strip=True)


def _extract_row(element, fields: list) -> dict:
    row: dict = {}
    for field in fields:
        if not isinstance(field, dict) or not field.get("name"):
            continue
        row[field["name"]] = _field_value(element, field)
    return row


def extract_rows(html: str, schema: dict | None) -> list | None:
    """Apply a CSS schema against already-fetched HTML.

    Returns the raw extracted row list (for cross-page merging), or None on
    failure. Schema shape (compatible with the schema format this tool has
    always accepted): `{"name", "baseSelector", "fields": [{"name",
    "selector", "type"}]}` with field `type` in text / attribute / html.
    """
    if not isinstance(html, str) or not html or not schema or not isinstance(schema, dict):
        return None
    fields = schema.get("fields")
    if not isinstance(fields, list) or not fields:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        base_selector = schema.get("baseSelector")
        elements = soup.select(base_selector) if base_selector else [soup]
        return [_extract_row(element, fields) for element in elements]
    except Exception as e:
        logger.warning("schema extraction failed: %s", e)
        return None


def extract_with_schema(html: str, schema: dict | None) -> str | None:
    """Apply a CSS schema against already-fetched HTML.

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
