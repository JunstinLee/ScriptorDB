from __future__ import annotations

import json

from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.inspect")

_INSPECT_JS = """\
(params) => {
  const extRe = /[.](pdf|xls|xlsx|zip|csv)([?#]|$)/i;
  const anchors = Array.from(document.querySelectorAll("a[href]")).filter((a) => extRe.test(a.href));
  const seen = new Map();
  for (const a of anchors) {
    let el = a.parentElement;
    while (el && el !== document.documentElement) {
      const text = (el.innerText || "").replace(/\\s+/g, " ").trim();
      if (text.length >= params.minText) {
        const classes = el.className ? String(el.className).trim().split(/\\s+/).join(".") : "";
        const key = el.tagName + (classes ? "." + classes : "");
        let rec = seen.get(key);
        if (!rec) {
          rec = {
            selector: el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (classes ? "." + classes : ""),
            hits: 0,
            links: 0,
            sampleText: "",
            sampleLinks: [],
          };
          seen.set(key, rec);
        }
        rec.hits++;
        rec.links++;
        if (!rec.sampleText) rec.sampleText = text.slice(0, params.maxSample);
        if (rec.sampleLinks.length < 3) rec.sampleLinks.push(a.href);
        break;
      }
      el = el.parentElement;
    }
  }
  const candidates = Array.from(seen.values())
    .filter((r) => r.links >= params.minLinks)
    .sort((x, y) => y.hits - x.hits)
    .slice(0, params.maxCandidates);
  return { documentLinkCount: anchors.length, candidates };
}
"""


@db_tool(name="browser_inspect_structure", category="browser", timeout=15, sequential=False)
async def browser_inspect_structure(
    ctx: RunContext[Settings],
    max_candidates: int = 8,
    min_links: int = 1,
    min_text: int = 5,
    max_sample: int = 300,
) -> str:
    """Discover candidate row containers on the current page (final JSON result).

    Scans the rendered DOM for document links (PDF/Excel/ZIP/CSV) and reports the
    containers that hold them, for orientation only. Row location is automatic:
    call `browser_extract_table` with no selectors — do not pass the candidate
    selectors shown here to any tool. The result is final data — no further parsing,
    transformation, or computation is needed.

    Parameters:
    - max_candidates: maximum number of container candidates returned;
    - min_links: minimum number of document links a container must hold to be reported;
    - min_text: minimum visible text length for a container to be considered a row;
    - max_sample: max characters of sample innerText included per candidate.
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    try:
        payload = await page_obj.evaluate(
            _INSPECT_JS,
            {
                "maxCandidates": max(max_candidates, 1),
                "minLinks": max(min_links, 0),
                "minText": max(min_text, 0),
                "maxSample": max(max_sample, 50),
            },
        )
    except Exception as e:
        manager.record_action("inspect_structure", f"error: {e}", success=False)
        return f"Structure inspection failed: {e}"

    if not isinstance(payload, dict):
        payload = {"documentLinkCount": 0, "candidates": []}

    candidates = [c for c in payload.get("candidates", []) if isinstance(c, dict)]
    manager.record_action("inspect_structure", f"{payload.get('documentLinkCount', 0)} doc links, {len(candidates)} candidates")

    if not candidates:
        return "No document-link row containers found on the page. The page may not have loaded yet or its documents use a different pattern."

    body = {
        "documentLinkCount": payload.get("documentLinkCount", 0),
        "candidates": candidates,
    }
    return f"Found {payload.get('documentLinkCount', 0)} document links; candidate row containers:\n{json.dumps(body, ensure_ascii=False)}"
