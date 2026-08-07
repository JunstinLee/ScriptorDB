from __future__ import annotations

import json

from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _click_next, _require_browser, _settle_after_click
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.table")

_TABLE_EXTRACT_JS = """\
(params) => {
  let docRe = /[.](pdf|xls|xlsx|zip|csv)([?#]|$)/i;
  if (params.linkPattern) {
    try { docRe = new RegExp(params.linkPattern, "i"); } catch (e) {}
  }
  const dateRe = /\\b(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{2,4}\\b|\\b\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}\\b/i;
  const textOf = (el) => (el.innerText || "").replace(/\\s+/g, " ").trim();
  const enough = (el) => {
    if (!el) return true;
    const t = textOf(el);
    if (t.length < params.minText) return false;
    if (params.requireDate && !dateRe.test(t)) return false;
    return true;
  };
  const grow = (el) => {
    let cur = el;
    while (cur && cur !== document.documentElement && !enough(cur)) {
      cur = cur.parentElement;
    }
    if (!cur || cur === document.documentElement) return null;
    return cur;
  };

  let rowEls = [];
  if (params.auto) {
    const seen = new Set();
    const anchors = Array.from(document.querySelectorAll("a[href]")).filter((a) => docRe.test(a.href || ""));
    for (const a of anchors) {
      const row = grow(a);
      if (row && !seen.has(row)) { seen.add(row); rowEls.push(row); }
    }
  } else {
    for (const row of Array.from(document.querySelectorAll(params.rowSelector))) {
      const grown = grow(row);
      if (grown) rowEls.push(grown);
    }
  }

  if (params.auto) {
    rowEls = rowEls.filter((row) => !rowEls.some((other) => other !== row && row.contains(other)));
  }

  const out = [];
  const seenKeys = new Set();
  for (const row of rowEls) {
    const rec = {};
    for (const name of Object.keys(params.fields)) {
      const spec = params.fields[name];
      let nodes = [];
      if (spec.selector) {
        try { nodes = row.querySelectorAll(spec.selector); } catch (e) {}
      } else {
        nodes = [row];
      }
      if (spec.doc) nodes = Array.from(nodes).filter((n) => docRe.test(n.href || ""));
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
    const key = JSON.stringify(rec);
    if (!seenKeys.has(key)) { seenKeys.add(key); out.push(rec); }
  }
  return out;
}
"""

_DEFAULT_FIELDS = {
    "text": {"selector": "", "attribute": "text"},
    "links": {"selector": "a[href]", "attribute": "href", "all": True, "doc": True},
}

_DEFAULT_LINK_PATTERN = "[.](pdf|xls|xlsx|zip|csv)([?#]|$)"


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


async def _extract_rows_from_page(
    page_obj,
    row_selector: str,
    fields: dict,
    min_text: int,
    link_pattern: str,
    require_date: bool,
) -> list[dict]:
    payload = await page_obj.evaluate(
        _TABLE_EXTRACT_JS,
        {
            "auto": not row_selector or row_selector.lower() == "auto",
            "rowSelector": row_selector,
            "fields": fields,
            "minText": min_text,
            "linkPattern": link_pattern,
            "requireDate": require_date,
        },
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
    min_text: int,
    link_pattern: str,
    require_date: bool,
) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for i in range(max_pages):
        page_rows = await _extract_rows_from_page(
            page_obj, row_selector, fields, min_text, link_pattern, require_date
        )
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


def _filter_blank_rows(rows: list[dict]) -> list[dict]:
    """Drop noise rows before reporting: blank text, or default-shaped rows with no document links."""
    cleaned: list[dict] = []
    for row in rows:
        if "text" in row and "links" in row:
            text = row.get("text")
            if isinstance(text, str) and text.strip() and row.get("links"):
                cleaned.append(row)
            continue
        if any(str(v).strip() for v in row.values() if v not in (None, "", [])):
            cleaned.append(row)
    return cleaned


def _format_result(rows: list[dict], max_pages: int, max_rows: int) -> str:
    truncated = False
    if len(rows) > max_rows:
        rows = rows[:max_rows]
        truncated = True
    body = {
        "total": len(rows),
        "pages": max(max_pages, 1),
        "truncated": truncated,
        "rows": rows,
    }
    return f"Extracted {len(rows)} structured rows (up to {max(max_pages, 1)} page(s)):\n{json.dumps(body, ensure_ascii=False)}"


@db_tool(name="browser_extract_table", category="browser", timeout=60, sequential=False)
async def browser_extract_table(
    ctx: RunContext[Settings],
    wait_for_selector: str = "",
    pagination_next_selector: str = "",
    max_pages: int = 1,
    page_settle_ms: int = 800,
    max_rows: int = 500,
    min_text: int = 30,
    link_pattern: str = "",
) -> str:
    """Extract structured rows from the rendered page, auto-discovering the rows (final JSON result).

    The tool locates the row containers itself: each document link is walked up to its
    first ancestor whose text is long enough and contains a date, then each row returns
    {text: the row's innerText, links: document hrefs inside the row}. Blank rows are
    filtered out before the result is reported. No CSS selectors or flags are needed —
    the tool decides, not you.

    The result is the final, directly presentable data (total/pages/truncated/rows).
    The returned rows are already cleaned and structured — no further parsing,
    transformation, or computation is needed; answer the user based on them directly.

    Parameters:
    - wait_for_selector: wait for this CSS selector before extracting (dynamically rendered pages);
    - pagination_next_selector: the "next page" selector of the site pager (auto-detects when
      left empty); with max_pages>1 it clicks through pages and merges rows from all pages;
    - page_settle_ms: settle time after pagination click (milliseconds);
    - max_rows: maximum number of rows returned (truncates if exceeded);
    - min_text: minimum visible text length for a row container; rows shorter than this are
      grown upward to their parent container;
    - link_pattern: custom regex (JS) to match document URLs, e.g. "[.]pdf|[.]docx" for sites
      without standard file extensions.
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    pattern = link_pattern.strip() or _DEFAULT_LINK_PATTERN
    try:
        if wait_for_selector:
            await page_obj.wait_for_selector(wait_for_selector, timeout=10000)

        probe = await _extract_rows_from_page(
            page_obj, "auto", _DEFAULT_FIELDS, max(min_text, 0), pattern, True
        )
        require_date = bool(probe)
        rows = await _extract_rows_across_site_pages(
            page_obj,
            "auto",
            _DEFAULT_FIELDS,
            pagination_next_selector,
            max(max_pages, 1),
            max(page_settle_ms, 0),
            max(min_text, 0),
            pattern,
            require_date,
        )
    except Exception as e:
        manager.record_action("extract_table", f"error: {e}", success=False)
        return f"Table extraction failed: {e}"

    rows = _filter_blank_rows(rows)
    manager.record_action("extract_table", f"{len(rows)} rows")
    if not rows:
        return "No rows found on page"
    return _format_result(rows, max_pages, max_rows)


@db_tool(name="browser_extract_rows", category="browser", timeout=60, sequential=False)
async def browser_extract_rows(
    ctx: RunContext[Settings],
    row_selector: str,
    fields: str = "",
    wait_for_selector: str = "",
    pagination_next_selector: str = "",
    max_pages: int = 1,
    page_settle_ms: int = 800,
    max_rows: int = 500,
    min_text: int = 30,
    link_pattern: str = "",
    require_date_token: bool = False,
) -> str:
    """Extract structured rows using an explicit CSS row selector and field mapping (advanced).

    Use this only when `browser_extract_table` returns no or wrong rows for an unusual
    page structure. Returns the final JSON data (total/pages/truncated/rows); the returned
    rows are already cleaned and structured — no further parsing, transformation, or
    computation is needed.

    Parameters:
    - row_selector: CSS selector for each row container (required). Rows shorter than
      `min_text` are automatically grown upward to their parent container;
    - fields: JSON field mapping, format:
        {"date": {"selector": ".date"}, "pdf": {"selector": "a[href$='.pdf']", "attribute": "href"}}
      attribute values: text (default), href (resolved to absolute URL), or any HTML attribute name;
      "all": true collects all matches for that field as an array.
      When left empty, each row returns {text: the row's innerText, links: document hrefs inside the row}.
    - wait_for_selector / pagination_next_selector / page_settle_ms / max_rows / min_text /
      link_pattern / require_date_token: same meaning as in `browser_extract_table`.
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    parsed_fields = _parse_fields(fields)
    if parsed_fields is None:
        return "Invalid fields: expected a non-empty JSON object like {\"date\": {\"selector\": \".date\"}, \"pdf\": {\"selector\": \"a[href$='.pdf']\", \"attribute\": \"href\"}}"

    pattern = link_pattern.strip() or _DEFAULT_LINK_PATTERN
    try:
        if wait_for_selector:
            await page_obj.wait_for_selector(wait_for_selector, timeout=10000)
        rows = await _extract_rows_across_site_pages(
            page_obj,
            row_selector.strip(),
            parsed_fields,
            pagination_next_selector,
            max(max_pages, 1),
            max(page_settle_ms, 0),
            max(min_text, 0),
            pattern,
            bool(require_date_token),
        )
    except Exception as e:
        manager.record_action("extract_rows", f"error: {e}", success=False)
        return f"Row extraction failed: {e}"

    rows = _filter_blank_rows(rows)
    manager.record_action("extract_rows", f"{len(rows)} rows")
    if not rows:
        return "No rows found on page"
    return _format_result(rows, max_pages, max_rows)
