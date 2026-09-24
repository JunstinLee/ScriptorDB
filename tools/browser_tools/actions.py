from __future__ import annotations

import time

from config.settings import Settings
from pydantic_ai import RunContext
from tools.browser_common import (
    _check_blocked,
    _ensure_downloads_dir,
    _require_browser,
    _settle_after_click,
    _wait_for_download,
)
from tools.browser_tools.selectors import (
    _ACTION_TIMEOUT_MS,
    _is_engine_selector,
    _normalize_selector,
)
from tools.tool_decorators import db_tool


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
    failed = "failed" in str(result).lower() or "error" in str(result).lower()
    if failed:
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
