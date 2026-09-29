from __future__ import annotations

from config.settings import Settings
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import _check_blocked, _require_browser
from tools.browser_tools.selectors import _normalize_selector
from tools.tool_decorators import db_tool


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
    snippet = (el.get("text") or el.get("value") or "").strip()
    label = f" {snippet[:40]!r}" if snippet else ""
    return (
        f"{index}. <{el.get('tag')}> [{el.get('role') or el.get('tag')}]"
        f"{label} -> {el.get('selector')}{suffix}"
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
        )
    if scope == "container":
        return (
            f"No interactive elements in the active container{suffix}. "
            "Wait for the panel to appear (browser_wait_for_selector) and retry; use "
            'scope="page" only as a last resort — it applies a candidate cap and may be incomplete.'
        )
    return f"No interactive elements found.{suffix}"


@db_tool(name="browser_get_text", category="browser", timeout=15, sequential=True)
async def browser_get_text(ctx: RunContext[Settings]) -> str:
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    title = await page.title()
    text = await page.inner_text("body")
    result = f"# {title}\n\n{text}"
    manager.record_action("get_text", f"Retrieved {len(result)} chars")
    return result


@db_tool(name="browser_locate", category="browser", timeout=15, sequential=False)
async def browser_locate(
    ctx: RunContext[Settings],
    text: str = "",
    role: str = "",
    scope: str = "visible",
) -> str:
    """List interactive elements on the current page with ready-to-reuse selectors.

    Use this to discover what is clickable or fillable before acting. Each line ends
    with a `selector` that can be passed straight back to `browser_click`/`browser_fill`
    (ex. `text=导出`, `#id`, `input[name="…"]`). Optionally filter by `text` (substring
    of the element's text) or `role` (button/textbox/tab/link/combobox/...). Read-only:
    this tool does not change the page.

    The main list contains only elements Playwright confirmed as **usable right now**
    (visible, enabled, and actually receiving pointer events). Elements confirmed
    unusable (hidden / disabled / covered) are omitted. When nothing qualifies, the tool
    degrades to elements it could not verify, each tagged `[unverified]` with a trailing
    count — confirm those (browser_wait_for_selector / browser_query) before acting.

    `scope` chooses how wide to scan: `"visible"` (default) exposes only components in
    the current viewport within the active container, so hidden sibling panels (ex. the
    inactive month-panel of a date picker) are excluded; widen to `"container"` to keep
    the whole active container (including slightly off-screen parts) or `"page"` to scan
    the entire DOM. Hidden elements only appear at `scope="page"`. `scope="page"` applies
    a candidate cap, so its result may be incomplete.
    """
    from browser.runtime import locate_elements

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    scope = (scope or "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"

    elements = await locate_elements(page, text=text, role=role, scope=scope)
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
            "inspect with browser_query before acting.]"
        )
        return "\n".join(lines)

    hint = _empty_elements_hint(scope, filters)
    if blocked:
        hint += (
            f"\n[{blocked} matching element(s) exist but are currently hidden, "
            "disabled, or covered.]"
        )
    return hint


@db_tool(name="browser_query", category="browser", timeout=10, sequential=False)
async def browser_query(
    ctx: RunContext[Settings],
    selector: str,
    attribute: str = "",
    all: bool = False,
) -> str | ToolResult:
    """Read the text (or an attribute) of elements matching `selector`.

    `selector` accepts both CSS and Playwright engine selectors: `#id`, `.class`,
    `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    Pass `attribute` (e.g. `href`, `value`) to read an attribute instead of text,
    and `all=True` to return every match.
    """
    from browser.runtime import get_image_sources, query_attr, query_attr_all, query_text, query_text_all
    from browser.runtime import InvalidSelectorError
    from browser.sensitive import is_password_control

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    selector = _normalize_selector(selector)

    try:
        if selector == "img[src]" and attribute == "src" and all:
            result = await get_image_sources(page)
            manager.record_action("query", selector)
            return result

        if attribute:
            if attribute == "value" and await is_password_control(page, selector):
                # 密码控件（系统凭证已由 autofill 填入）：不读 DOM value，
                # 返回占位；all=True 对 selector 首元素判定一次，命中整组占位。
                result = "[redacted: password field]"
            elif all:
                result = await query_attr_all(page, selector, attribute)
            else:
                result = await query_attr(page, selector, attribute)
        elif all:
            result = await query_text_all(page, selector)
        else:
            result = await query_text(page, selector)
    except InvalidSelectorError as e:
        manager.record_action("query", selector, success=False)
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="invalid_selector",
                message=(
                    f"Invalid selector '{selector}': {e}. Use a CSS selector or a "
                    'Playwright engine selector such as li:has-text("…") or text=…'
                ),
            ),
        )

    manager.record_action("query", selector)
    return result


@db_tool(name="browser_evaluate", category="browser", timeout=15, sequential=False)
async def browser_evaluate(ctx: RunContext[Settings], js: str) -> str:
    from browser.runtime import evaluate as _eval
    from browser.sensitive import current_site_password
    from runtime.redact import redact

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    pwd = current_site_password(
        page.url, ctx.deps.workspace_id if ctx.deps else None
    )
    if pwd is not None and pwd in js:
        # 脚本携带系统站点密码：禁止读取或回写密码字段。
        return "Refused: the script contains the system site password; password fields must not be read or written"
    result = await _eval(page, js)
    result = redact(result)
    manager.record_action("evaluate", js[:50] + "..." if len(js) > 50 else js)
    return result
