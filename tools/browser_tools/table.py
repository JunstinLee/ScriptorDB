from __future__ import annotations

import json

from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser import _check_blocked, _click_next, _require_browser, _settle_after_click
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.table")

_TABLE_EXTRACT_JS = """\
(params) => {
  const rows = document.querySelectorAll(params.rowSelector);
  const out = [];
  for (const row of rows) {
    const rec = {};
    for (const name of Object.keys(params.fields)) {
      const spec = params.fields[name];
      let nodes = [];
      if (spec.selector) {
        try { nodes = row.querySelectorAll(spec.selector); } catch (e) {}
      } else {
        nodes = [row];
      }
      const attr = spec.attribute || "text";
      const pick = (el) => {
        if (!el) return "";
        if (attr === "text") return (el.textContent || "").trim();
        if (attr === "href") return el.href || "";
        return el.getAttribute(attr) || "";
      };
      if (spec.all) {
        rec[name] = Array.from(nodes).map(pick);
      } else {
        rec[name] = pick(nodes[0]);
      }
    }
    out.push(rec);
  }
  return out;
}
"""

_DEFAULT_FIELDS = {
    "text": {"selector": "", "attribute": "text"},
    "links": {"selector": "a[href]", "attribute": "href", "all": True},
}


def _parse_fields(raw: str) -> dict | None:
    if not raw.strip():
        return _DEFAULT_FIELDS
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or not obj:
        return None
    for name, spec in obj.items():
        if not isinstance(name, str) or not isinstance(spec, dict):
            return None
    return obj


async def _extract_rows_from_page(page_obj, row_selector: str, fields: dict) -> list[dict]:
    payload = await page_obj.evaluate(
        _TABLE_EXTRACT_JS,
        {"rowSelector": row_selector, "fields": fields},
    )
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


async def _extract_rows_across_site_pages(
    page_obj,
    row_selector: str,
    fields: dict,
    pagination_next_selector: str,
    max_pages: int,
    page_settle_ms: int,
) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for i in range(max_pages):
        page_rows = await _extract_rows_from_page(page_obj, row_selector, fields)
        new_rows = []
        for row in page_rows:
            key = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                new_rows.append(row)
        rows.extend(new_rows)
        if i < max_pages - 1:
            if not await _click_next(page_obj, pagination_next_selector):
                break
            await _settle_after_click(page_obj)
        if not new_rows and i > 0:
            break
    return rows


@db_tool(name="browser_extract_table", category="browser", timeout=60, sequential=False)
async def browser_extract_table(
    ctx: RunContext[Settings],
    row_selector: str,
    fields: str = "",
    wait_for_selector: str = "",
    pagination_next_selector: str = "",
    max_pages: int = 1,
    page_settle_ms: int = 800,
    max_rows: int = 500,
) -> str:
    """Extract structured data by rows (with automatic pagination merge), returning a final JSON result.

    The result is the final, directly presentable data (total/pages/truncated/rows).
    Answer the user based on it directly; do not re-process it with run_python_code.

    Parameters:
    - row_selector: CSS selector for each row container (required). Works for any container
      (div, li, tr, ...) — no need to know the exact sub-selectors beforehand.
    - fields: optional JSON field mapping, format:
        {"date": {"selector": ".date"}, "pdf": {"selector": "a[href$='.pdf']", "attribute": "href"}}
      attribute values: text (default), href (resolved to absolute URL), or any HTML attribute name;
      "all": true collects all matches for that field as an array.
      When left empty, each row returns {text: the row's innerText, links: all hrefs inside the row},
      which keeps every row's own content and document links together.
    - wait_for_selector: wait for this selector before extracting (dynamically rendered pages);
    - pagination_next_selector: the "next page" selector of the site pager (auto-detects when
      left empty); with max_pages>1 it clicks through pages and merges rows from all pages;
    - page_settle_ms: settle time after pagination click (milliseconds);
    - max_rows: maximum number of rows returned (truncates if exceeded).
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    parsed_fields = _parse_fields(fields)
    if parsed_fields is None:
        return "Invalid fields: expected a non-empty JSON object like {\"date\": {\"selector\": \".date\"}, \"pdf\": {\"selector\": \"a[href$='.pdf']\", \"attribute\": \"href\"}}"

    try:
        if wait_for_selector:
            await page_obj.wait_for_selector(wait_for_selector, timeout=10000)
        rows = await _extract_rows_across_site_pages(
            page_obj,
            row_selector,
            parsed_fields,
            pagination_next_selector,
            max(max_pages, 1),
            max(page_settle_ms, 0),
        )
    except Exception as e:
        manager.record_action("extract_table", f"error: {e}", success=False)
        return f"Table extraction failed: {e}"

    truncated = False
    if len(rows) > max_rows:
        rows = rows[:max_rows]
        truncated = True

    manager.record_action("extract_table", f"{len(rows)} rows")
    if not rows:
        return "No rows found on page"

    body = {
        "total": len(rows),
        "pages": max(max_pages, 1),
        "truncated": truncated,
        "rows": rows,
    }
    return f"Extracted {len(rows)} structured rows (up to {max(max_pages, 1)} page(s)):\n{json.dumps(body, ensure_ascii=False)}"
