"""动作类工具：click / select_option / press_key / scroll / wait_for_selector。

填写类工具见 :mod:`tools.browser_tools.fill`；ref 的执行期校验见
:mod:`browser.ref_verify`（此处仅 re-export ``_resolve_ref_target`` 供动作工具使用）。
"""

from __future__ import annotations

import time

from browser.ref_verify import _resolve_ref_target  # noqa: F401  (re-export for tools/tests)
from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import (
    _check_blocked,
    _click_may_download,
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

logger = get_logger(__name__)

# browser_click 的下载等待默认秒数。等于该值时走「按需判断」（见 _click_may_download）；
# 显式传其它正值则强制等待，0 跳过等待。
_DEFAULT_DOWNLOAD_WAIT = 2


def _click_error_category(message: str) -> str:
    low = message.lower()
    if "not found" in low:
        return "resource_not_found"
    if "not visible" in low or "is disabled" in low or "not actionable" in low:
        return "not_actionable"
    # 遮挡要先于超时判定：被别的元素挡住时 page.click 也抛 PlaywrightTimeoutError，
    # 文案里同时含 "timed out" 与 "covered"，先匹配超时会把遮挡误报成超时。
    if "covered" in low or "intercepts pointer events" in low:
        return "element_covered"
    if "timed out" in low or "timeout" in low:
        return "execution_timeout"
    return "internal_error"


def _format_click_target(target: dict) -> str:
    tag = target.get("tag") or ""
    role = target.get("role") or tag
    text = (target.get("text") or target.get("ariaLabel") or "").strip()
    value = (target.get("value") or "").strip()
    label = f" {text[:40]!r}" if text else ""
    val = f" value={value[:40]!r}" if value else ""
    return f"Target: <{tag}> [{role}]{label}{val}"


def _format_snapshot_field(field: dict) -> str:
    name = (field.get("label") or field.get("placeholder") or "").strip()
    selector = field.get("selector") or ""
    value = field.get("value") or ""
    line = f"{name!r} -> {selector} (value={value!r})"
    options = field.get("options")
    if options:
        opts = ", ".join(
            repr(str(o.get("value"))) for o in options if isinstance(o, dict)
        )
        line += f" options=[{opts}]"
    return line


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
        await highlight_click(page, selector, block=False)
    manager.record_action("wait_for_selector", selector, selector=selector)
    return result


@db_tool(name="browser_click", category="browser", timeout=15, sequential=True)
async def browser_click(
    ctx: RunContext[Settings],
    selector: str = "",
    text: str = "",
    ref: str = "",
    download_wait: int = _DEFAULT_DOWNLOAD_WAIT,
) -> str | ToolResult:
    """Click the first element matching `selector` (or the element a `ref` points to).

    Prefer `ref` when you have one: pass the `ref` from `browser_find` and this tool
    locates the element directly without re-scanning the page. A ref is only valid
    while the page URL is unchanged; if it returns a `stale_ref` error the page has
    navigated — call `browser_find` again for a fresh ref (do not retry the old one).

    Otherwise `selector` accepts both CSS and Playwright engine selectors: `#id`,
    `.class`, `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    As a shortcut, pass `text="导出全部"` instead of a selector to click by text.
    If the click triggers a download, this waits up to `download_wait` seconds for the
    file to be saved to the workspace outputs dir and reports "Captured download" with
    its path when it arrives. Pass `download_wait=0` to skip the wait.
    """
    from browser.actions import click as _click
    from browser.highlights import highlight_click

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if (ref or "").strip():
        target = await _resolve_ref_target(manager, ref.strip())
        if isinstance(target, ToolResult):
            manager.record_action("click", f"stale ref {ref}", success=False)
            return target
        page, selector = target
    else:
        if not selector and text:
            selector = f"text={text}"
        if not selector:
            return ToolResult(
                success=False,
                error=ToolErrorInfo(
                    category="invalid_selector",
                    message="browser_click needs a `selector`, `text`, or `ref`.",
                ),
            )
        selector = _normalize_selector(selector)
    _ensure_downloads_dir(manager, ctx)
    if not _is_engine_selector(selector):
        await highlight_click(page, selector, block=False)
        await manager.trace.record_pre_click(page, selector)

    clicked_at = time.time()
    click_result = await _click(page, selector, timeout=_ACTION_TIMEOUT_MS)
    click_failed = click_result.startswith("Click failed")
    if click_failed:
        from browser.runtime import locate_elements

        candidates = await locate_elements(page, scope="visible")
        target = next((el for el in candidates if el.get("selector") == selector), None)
        container_key = target.get("containerKey") if target else None
        if container_key:
            candidates = [
                el for el in candidates
                if el.get("containerKey") == container_key
                and el.get("semantic") in ("calendar-day", "calendar-navigation", "calendar-month")
            ]
        else:
            candidates = [
                el for el in candidates
                if el.get("semantic") in ("calendar-day", "calendar-navigation", "calendar-month")
            ]
        if candidates:
            click_result += "\nCurrent calendar candidates: " + "; ".join(
                f"{el.get('text') or el.get('ariaLabel') or el.get('semantic')}"
                f" [{el.get('state')}]: {el.get('selector')}"
                for el in candidates[:20]
            )
    # 失败判定只看 click 执行结果，避免页面数据（快照里的 value 文本）误触发
    # record_element_failure / detect_takeover。
    failed = "failed" in click_result.lower() or "error" in click_result.lower()

    snapshot = await _settle_after_click(page, selector, quick=click_failed)
    lines = [click_result]
    if download_wait != 0:
        # 默认值走「按需判断」：只有可能下载的点击才等；显式传其它正值则强制等待。
        if download_wait == _DEFAULT_DOWNLOAD_WAIT:
            may_download = await _click_may_download(page, selector)
        else:
            may_download = True
        entry = await _wait_for_download(
            manager, clicked_at, download_wait, may_download=may_download
        )
        if entry and entry.get("ok"):
            lines.append(f"Captured download: {entry.get('filename')} ({entry.get('path')})")
        elif entry:
            lines.append(f"Warning: a download was triggered but not saved: {entry.get('reason')}")

    target = snapshot.get("target")
    if isinstance(target, dict):
        lines.append(_format_click_target(target))
    lines.append(f"Overlay: {snapshot.get('overlays', 0)} visible panel(s)")
    fields = snapshot.get("fields") or []
    if fields:
        lines.append("Fields: " + "; ".join(
            _format_snapshot_field(f) for f in fields if isinstance(f, dict)
        ))

    trace = await manager.trace.record_post_nav(page)
    detail = selector
    pre = trace.get("pre_click") or {}
    final_url = trace.get("final_url") or ""
    if final_url:
        lines.append(f"Page state: {final_url} ({trace.get('title') or ''})")
    if pre.get("url") and final_url and pre.get("url") != final_url:
        detail = f"{selector} -> {final_url}"
    result = "\n".join(lines)
    manager.record_action("click", detail, selector=selector,
                          success="Clicked" in result)
    if failed:
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    if click_failed:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category=_click_error_category(click_result),
                message=result,
            ),
        )
    return result


@db_tool(name="browser_select_option", category="browser", timeout=15, sequential=True)
async def browser_select_option(
    ctx: RunContext[Settings],
    selector: str = "",
    value: str = "",
    label: str = "",
    ref: str = "",
) -> str | ToolResult:
    """Select an option in the `<select>` matching `selector` (or the element a `ref` points to).

    Prefer `ref` when you have one: pass the `ref` from `browser_find` and the control is
    located directly without re-scanning. A ref is only valid while the page URL is
    unchanged; on a `stale_ref` error call `browser_find` again for a fresh ref.

    Pass `value` (the option's value attribute) or `label` (its visible text).
    """
    from browser.actions import select_option as _select
    from browser.highlights import highlight_input, highlight_input_remove

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if (ref or "").strip():
        target = await _resolve_ref_target(manager, ref.strip())
        if isinstance(target, ToolResult):
            manager.record_action("select_option", f"stale ref {ref}", success=False)
            return target
        page, selector = target
    elif not selector:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="invalid_selector",
                message="browser_select_option needs a `selector` or `ref`.",
            ),
        )
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


@db_tool(name="browser_scroll", category="browser", timeout=15, sequential=False, defer_loading=True)
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
