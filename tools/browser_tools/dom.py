from __future__ import annotations

import re
import time

from config.settings import Settings
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import _check_blocked, _ensure_downloads_dir, _require_browser, _settle_after_click, _wait_for_download
from tools.tool_decorators import db_tool

# Playwright 引擎选择器前缀（text=/xpath=/aria= 等）不是合法 CSS，
# 不能传给 document.querySelector —— 高亮/跟踪前先识别并跳过。
_PLAYWRIGHT_ENGINES = frozenset({
    "css", "xpath", "text", "id", "data-testid", "data-test", "data-test-id",
    "data-qa", "aria", "role", "nth", "internal",
})

# 动作层超时 = 工具超时（15s）- 余量：避免 Playwright 默认 30s 与 wrapper 同时到点。
_ACTION_TIMEOUT_MS = 12_000


def _is_engine_selector(selector: str) -> bool:
    match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*?)\s*=", selector)
    return bool(match) and match.group(1).lower() in _PLAYWRIGHT_ENGINES


_CONTAINS_RE = re.compile(r""":contains\(\s*(['"])(.*?)\1\s*\)""")


def _normalize_selector(selector: str) -> str:
    """把 jQuery 的 :contains("x") 归一化为 Playwright 的 :has-text("x")。"""
    return _CONTAINS_RE.sub(lambda m: f':has-text("{m.group(2)}")', selector)


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
) -> str:
    """List interactive elements on the current page with ready-to-reuse selectors.

    Use this to discover what is clickable or fillable before acting. Each line ends
    with a `selector` that can be passed straight back to `browser_click`/`browser_fill`
    (ex. `text=导出`, `#id`, `input[name="…"]`). Optionally filter by `text` (substring
    of the element's text) or `role` (button/textbox/tab/link/combobox/...). Read-only:
    this tool does not change the page.
    """
    from browser.runtime import locate_elements

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    elements = await locate_elements(page, text=text, role=role)
    filters = []
    if text:
        filters.append(f"text={text}")
    if role:
        filters.append(f"role={role}")
    if not elements:
        suffix = f" (filter: {', '.join(filters)})" if filters else ""
        return f"No interactive elements found.{suffix}"

    lines = []
    for i, el in enumerate(elements, 1):
        snippet = (el.get("text") or el.get("value") or "").strip()
        label = f" {snippet[:40]!r}" if snippet else ""
        lines.append(
            f"{i}. <{el.get('tag')}> [{el.get('role') or el.get('tag')}]{label} -> {el.get('selector')}"
        )
    manager.record_action(
        "locate",
        f"{len(elements)} elements" + (f" ({', '.join(filters)})" if filters else ""),
    )
    return "\n".join(lines)


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


@db_tool(name="browser_wait_for_selector", category="browser", timeout=15, sequential=True)
async def browser_wait_for_selector(
    ctx: RunContext[Settings],
    selector: str,
    state: str = "attached",
) -> str:
    """Wait for `selector` to reach `state` (attached/detached/visible/hidden).

    `selector` accepts both CSS and Playwright engine selectors: `#id`, `.class`,
    `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    Use `state="visible"` when you need the element to be actually shown.
    """
    from browser.context import wait_for_selector as _wait
    from browser.highlights import highlight_click

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    selector = _normalize_selector(selector)
    result = await _wait(page, selector, state)  # type: ignore[arg-type]
    if not _is_engine_selector(selector):
        await highlight_click(page, selector)
    manager.record_action("wait_for_selector", selector, selector=selector)
    return result


@db_tool(name="browser_click", category="browser", timeout=15, sequential=True)
async def browser_click(
    ctx: RunContext[Settings],
    selector: str,
    text: str = "",
    download_wait: int = 30,
) -> str:
    """Click the first element matching `selector`.

    `selector` accepts both CSS and Playwright engine selectors: `#id`, `.class`,
    `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    As a shortcut, pass `text="导出全部"` instead of a selector to click by text.
    If the click triggers a download, this waits up to `download_wait` seconds for the
    file to be saved to the workspace outputs dir and reports "Captured download" with
    its path when it arrives. Pass `download_wait=0` to skip the wait.
    """
    from browser.actions import click as _click
    from browser.highlights import highlight_click

    if not selector and text:
        selector = f"text={text}"
    selector = _normalize_selector(selector)
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    _ensure_downloads_dir(manager, ctx)
    if not _is_engine_selector(selector):
        await highlight_click(page, selector)
        await manager.trace.record_pre_click(page, selector)

    clicked_at = time.time()
    result = await _click(page, selector, timeout=_ACTION_TIMEOUT_MS)

    await _settle_after_click(page)
    if download_wait > 0:
        entry = await _wait_for_download(manager, clicked_at, download_wait)
        if entry and entry.get("ok"):
            result += f"\nCaptured download: {entry.get('filename')} ({entry.get('path')})"
        elif entry:
            result += f"\nWarning: a download was triggered but not saved: {entry.get('reason')}"
    trace = await manager.trace.record_post_nav(page)
    detail = selector
    pre = trace.get("pre_click") or {}
    final_url = trace.get("final_url") or ""
    if pre.get("url") and final_url and pre.get("url") != final_url:
        detail = f"{selector} -> {final_url}"
    manager.record_action("click", detail, selector=selector,
                          success="Clicked" in result)
    if "failed" in str(result).lower() or "error" in str(result).lower():
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    return result


@db_tool(name="browser_fill", category="browser", timeout=15, sequential=True)
async def browser_fill(ctx: RunContext[Settings], selector: str, text: str) -> str:
    """Fill the field matching `selector` with `text`.

    `selector` accepts CSS and Playwright engine selectors (`#id`,
    `input[placeholder="…"]`, `role=textbox[name="…"]`). Filling a read-only or
    disabled field fails immediately; use the page's own widget (e.g. a date
    picker) for such fields instead.
    """
    from browser.highlights import highlight_input, highlight_input_remove
    from browser.sensitive import current_site_password, is_password_control

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    selector = _normalize_selector(selector)
    pwd = current_site_password(
        page.url, ctx.deps.workspace_id if ctx.deps else None
    )
    if (
        await is_password_control(page, selector)
        and pwd is not None
        and pwd in text
    ):
        # 密码控件且内容为系统密码：系统已自动填充，跳过二次填写。
        # 不执行 record_element_failure/detect_takeover（非页面故障）。
        manager.record_action(
            "fill", "skipped (system-filled password)",
            selector=selector, success=True,
        )
        return "This password was filled automatically by the system; do not fill it again"
    from browser.actions import fill as _fill
    if not _is_engine_selector(selector):
        await highlight_input(page, selector)
    try:
        result = await _fill(page, selector, text, timeout=_ACTION_TIMEOUT_MS)
    finally:
        await highlight_input_remove(page)
    manager.record_action("fill", selector, selector=selector,
                          success="Filled" in result)
    if "not editable" not in str(result).lower() and (
        "failed" in str(result).lower() or "error" in str(result).lower()
    ):
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    return result


@db_tool(name="browser_select_option", category="browser", timeout=15, sequential=True)
async def browser_select_option(
    ctx: RunContext[Settings],
    selector: str,
    value: str = "",
    label: str = "",
) -> str:
    from browser.actions import select_option as _select
    from browser.highlights import highlight_input, highlight_input_remove

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if not value and not label:
        return "browser_select_option requires a value or a label"
    if not _is_engine_selector(selector):
        await highlight_input(page, selector)
    try:
        result = await _select(page, selector, value=value, label=label, timeout=_ACTION_TIMEOUT_MS)
    finally:
        await highlight_input_remove(page)
    manager.record_action("select_option", f"{selector} = {value or label}", selector=selector,
                          success="Selected" in result)
    if "failed" in str(result).lower() or "error" in str(result).lower():
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    return result


@db_tool(name="browser_press_key", category="browser", timeout=15, sequential=True)
async def browser_press_key(ctx: RunContext[Settings], key: str) -> str:
    from browser.actions import press_key as _press

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _press(page, key)
    manager.record_action("press_key", key)
    return result


@db_tool(name="browser_scroll", category="browser", timeout=15, sequential=False)
async def browser_scroll(
    ctx: RunContext[Settings],
    to_bottom: bool = True,
    pixels: int = 0,
) -> str:
    from browser.actions import scroll_by, scroll_to_bottom
    from browser.highlights import highlight_scroll

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    if to_bottom:
        result = await scroll_to_bottom(page)
        await highlight_scroll(page, 9999)
    elif pixels == 0:
        return "pixels must be non-zero when to_bottom is False"
    else:
        result = await scroll_by(page, pixels)
        await highlight_scroll(page, pixels)

    manager.record_action("scroll", "bottom" if to_bottom else f"{pixels}px")
    return result
