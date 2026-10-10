"""browser_find：元素 / 容器发现（只读）。

两态：默认 ``mode="elements"`` 列出可交互元素并铸造 ref；``mode="containers"``
扫描承载文档链接的容器，仅作方向参考。
"""

from __future__ import annotations

from browser.refs import mint_ref
from config.settings import Settings
from pydantic_ai import RunContext
from runtime.tool_middleware import (
    _content_revision,
    _find_fingerprint,
    _nav_revision,
    _page_key,
    _page_url,
    record_find,
)
from tools.browser_common import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

# 身份可证的定位器种类：只有这些定位串能保证解析回同一节点，才配铸造 ref。
# 弱种类（text / path）会让执行期的签名比较作用到别的节点上，索性不铸 ref。
_STRONG_LOCATOR_KINDS = {"data", "id", "name", "aria"}


def _state_counts(elements: list[dict]) -> tuple[int, int, int]:
    """统计 usable / blocked / unverified 三态计数。"""
    usable = blocked = unverified = 0
    for el in elements:
        state = el.get("state")
        if state == "usable":
            usable += 1
        elif state == "blocked":
            blocked += 1
        elif state == "unverified":
            unverified += 1
    return usable, blocked, unverified


def _blocked_reason_counts(elements: list[dict]) -> dict[str, int]:
    """blocked 条目的原因分布（hidden / disabled / covered / detached）。"""
    reasons: dict[str, int] = {}
    for el in elements:
        if el.get("state") == "blocked":
            reason = el.get("state_reason") or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
    return reasons


def _format_element_line(index: int, el: dict, suffix: str = "") -> str:
    text = (el.get("text") or "").strip()
    value = (el.get("value") or "").strip()
    snippet = text or value
    label = f" {snippet[:40]!r}" if snippet else ""
    semantic = el.get("semantic")
    sem = f" <{semantic}>" if semantic else ""
    val = f" value={value[:40]!r}" if value and text else ""
    target = el.get("ref") or ""
    if not target:
        anchor = snippet[:40]
        selector = (el.get("selector") or "").strip()
        state = el.get("state")
        parts = [f"text={anchor!r}"] if anchor else []
        if selector:
            note = "dynamic locator" if state == "usable" else "unverified"
            parts.append(f"{selector} ({note})")
        if not parts:
            parts.append(
                "(no reusable ref — pass the selector above straight to "
                "browser_click/browser_fill, or re-run browser_find after the panel settles)"
                if state == "usable"
                else "(unverified — no reusable handle; wait for it to settle then re-run browser_find)"
            )
        target = " / ".join(parts)
    return (
        f"{index}. <{el.get('tag')}> [{el.get('role') or el.get('tag')}]{sem}"
        f"{label}{val} -> {target}{suffix}"
    )


_REUSE_REF_HINT = (
    " If you already hold a `ref` for the target from an earlier browser_find, "
    "pass that ref to the action tool directly instead of scanning again."
)


def _empty_elements_hint(scope: str, filters: list[str]) -> str:
    suffix = f" (filter: {', '.join(filters)})" if filters else ""
    if scope == "visible":
        return (
            f"No interactive elements in the current visible layer{suffix}. "
            "Results are filtered to the current viewport and active container, so "
            "hidden sibling panels and off-screen nodes are excluded. Wait for the "
            "panel to settle (browser_wait_for_selector), or retry with "
            'scope="container" for the whole active container.'
            + _REUSE_REF_HINT
        )
    if scope == "container":
        return (
            f"No interactive elements in the active container{suffix}. "
            "Wait for the panel to appear (browser_wait_for_selector) and retry; use "
            'scope="page" only as a last resort — it applies a candidate cap and may be incomplete.'
            + _REUSE_REF_HINT
        )
    return f"No interactive elements found.{suffix}{_REUSE_REF_HINT}"


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


@db_tool(name="browser_find", category="browser", timeout=15, sequential=False)
async def browser_find(
    ctx: RunContext[Settings],
    text: str = "",
    role: str = "",
    scope: str = "visible",
    mode: str = "elements",
    quick: bool = False,
    max_candidates: int = 8,
    min_links: int = 1,
    min_text: int = 5,
    max_sample: int = 300,
):
    """Find things on the current page. Read-only: this tool does not change the page.

    `mode="elements"` (default) lists interactive elements with ready-to-reuse refs.
    Use this to discover what is clickable or fillable before acting. Each line ends
    with a `ref` (ex. `ref_<from browser_find>`) that can be passed straight back to
    `browser_click`/`browser_fill`/`browser_select_option`. A ref is valid only while
    the page stays on the same URL; after navigation or a full-page reload it goes
    stale and must be re-obtained. If a stale error comes back, call `browser_find`
    again. Optionally filter by `text` (substring of the element's text) or `role`
    (button/textbox/tab/link/combobox/...). If a call comes back with a `[Middleware]`
    find-repeat marker instead of results, the same query was already answered on the
    current page — reuse the refs you already hold rather than scanning again.

    The main list contains only elements Playwright confirmed as **usable right now**
    (visible, enabled, and actually receiving pointer events). Elements confirmed
    unusable (hidden / disabled / covered) are omitted. When nothing qualifies, the tool
    degrades to elements it could not verify, each tagged `[unverified]` with a trailing
    count — confirm those (browser_wait_for_selector / browser_read) before acting.

    `scope` chooses how wide to scan: `"visible"` (default) exposes only components in
    the current viewport within the active container, so hidden sibling panels (ex. the
    inactive month-panel of a date picker) are excluded; widen to `"container"` to keep
    the whole active container (including slightly off-screen parts) or `"page"` to scan
    the entire DOM. Hidden elements only appear at `scope="page"`. `scope="page"` applies
    a candidate cap, so its result may be incomplete.

    Pass `quick=True` for a lightweight scan that confirms fewer candidates — useful when
    you just want to find an entry point or a button. Calls with no `text`/`role` default
    to `quick=True`.

    `mode="containers"` scans the rendered DOM for document links (PDF/Excel/ZIP/CSV)
    and reports the containers that hold them, for orientation only. Row location is
    automatic: call `browser_extract_table` with no selectors — do not pass the candidate
    selectors shown here to any tool. The result is final data — no further parsing,
    transformation, or computation is needed.
    """
    if (mode or "elements").strip().lower() == "containers":
        return await _find_containers(ctx, max_candidates, min_links, min_text, max_sample)
    return await _find_elements(ctx, text, role, scope, quick)


async def _find_elements(ctx, text: str, role: str, scope: str, quick: bool = False):
    from browser.runtime import locate_elements

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    scope = (scope or "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"
    # 无 text/role 的"找入口/找按钮"场景采用更保守默认：走轻量模式，少确认候选。
    if not (text or "").strip() and not (role or "").strip():
        quick = True

    elements = await locate_elements(page, text=text, role=role, scope=scope, quick=quick)
    # 只为 Playwright 已确认可用的元素铸造 ref；unverified 保持原有降级输出。
    # run_id 取 deps.run_id（一次逻辑 run 恒定），不可取 ctx.run_id —— 后者每次
    # agent.run 都会变，审批暂停/恢复的续跑会换新值。
    run_id = ctx.deps.run_id if ctx.deps else ""
    for el in elements:
        if el.get("state") != "usable":
            continue
        kind = el.get("locatorKind") or "path"
        if kind not in _STRONG_LOCATOR_KINDS:
            continue
        el["ref"] = mint_ref(
            page, el.get("selector") or "", el.get("signature") or "", run_id,
            locator_kind=kind,
        )
    # 回写本次 find 的结果供 middleware 做重复调用熔断（evaluate_call 在工具前调用，
    # 拿不到结果，只能由工具层产出后回写）。
    record_find(
        ctx,
        page_key=_page_key(manager),
        page_url=_page_url(manager),
        nav_rev=_nav_revision(manager),
        fingerprint=_find_fingerprint(text, role, scope, _content_revision(manager)),
        produced=any(el.get("state") == "usable" for el in elements),
    )
    filters = []
    if text:
        filters.append(f"text={text}")
    if role:
        filters.append(f"role={role}")

    usable, blocked, unverified = _state_counts(elements)
    detail = f"scope={scope}"
    if filters:
        detail += f", {', '.join(filters)}"
    stats = (
        f"{len(elements)} elements ({detail}; "
        f"usable={usable}, blocked={blocked}, unverified={unverified})"
    )
    reasons = _blocked_reason_counts(elements)
    if reasons:
        stats += " blocked_reasons=" + ", ".join(
            f"{name}={count}" for name, count in sorted(reasons.items())
        )
    manager.record_action("locate", stats)

    if usable:
        return "\n".join(
            _format_element_line(i, el)
            for i, el in enumerate(
                (e for e in elements if e.get("state") == "usable"), 1
            )
        )

    if unverified:
        unverified_elements = [el for el in elements if el.get("state") == "unverified"]
        lines = [
            _format_element_line(i, el, " [unverified]")
            for i, el in enumerate(unverified_elements, 1)
        ]
        lines.append(
            f"[{len(unverified_elements)} unverified element(s): Playwright could not confirm "
            "them as ready to use. Wait for the page to settle (browser_wait_for_selector) or "
            "inspect with browser_read before acting.]"
        )
        return "\n".join(lines)

    hint = _empty_elements_hint(scope, filters)
    if blocked:
        hint += (
            f"\n[{blocked} matching element(s) exist but are currently hidden, "
            "disabled, or covered.]"
        )
    return hint


async def _find_containers(
    ctx,
    max_candidates: int,
    min_links: int,
    min_text: int,
    max_sample: int,
) -> dict:
    manager, page_obj = _require_browser()
    if page_obj is None:
        return {"error": "Browser not launched. Please call browser_launch first."}
    if blocked := _check_blocked(manager):
        return {"error": blocked}

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
        return {"error": f"Structure inspection failed: {e}"}

    if not isinstance(payload, dict):
        payload = {"documentLinkCount": 0, "candidates": []}

    candidates = [c for c in payload.get("candidates", []) if isinstance(c, dict)]
    manager.record_action(
        "inspect_structure",
        f"{payload.get('documentLinkCount', 0)} doc links, {len(candidates)} candidates",
    )

    return {
        "documentLinkCount": payload.get("documentLinkCount", 0),
        "candidates": candidates,
    }
