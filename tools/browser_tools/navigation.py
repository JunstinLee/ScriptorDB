from __future__ import annotations

import asyncio
import time

from browser import get_manager
from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser, _settle_after_click
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.navigation")

# browser_launch 与 browser_navigate 同刻发起时，navigate 最多等启动就绪的秒数。
_LAUNCH_READY_TIMEOUT = 20.0


async def _wait_for_launch_ready(manager, timeout: float = _LAUNCH_READY_TIMEOUT):
    """若 browser_launch 正在启动中，等它就绪后返回该 page；否则返回 None。

    只处理"启动进行中"的竞态：未启动且没有启动在途时立即返回 None，保持
    "Browser not launched" 的既有对外契约。
    """
    if not getattr(manager, "_launching", False) and not manager.is_launched():
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if manager.is_launched():
            page = manager.page()
            if page is not None:
                return page
        if not getattr(manager, "_launching", False) and not manager.is_launched():
            return None
        await asyncio.sleep(0.1)
    return None


@db_tool(name="browser_launch", category="browser", timeout=30, sequential=True)
async def browser_launch(ctx: RunContext[Settings], url: str = "") -> str:
    """Launch the browser and, if `url` is given, navigate to it in the same call.

    Pass `url` to open the starting page directly — this replaces the usual
    `browser_launch` followed by `browser_navigate` pair with a single call.
    """
    from config.workspace_paths import workspace_outputs_dir

    manager = get_manager()
    manager.cancel_idle_close()
    logger.info("browser_launch called")
    if ctx.deps and ctx.deps.workspace_path:
        manager.set_downloads_dir(workspace_outputs_dir(ctx.deps.workspace_path))
    result = await manager.launch()
    manager.record_action("launch", result)
    target = (url or "").strip()
    if target:
        nav_result = await browser_navigate(ctx, target)
        return f"{result}\n{nav_result}"
    return result


@db_tool(name="browser_navigate", category="browser", timeout=30, sequential=True)
async def browser_navigate(ctx: RunContext[Settings], url: str) -> str:
    from browser.context import navigate as _navigate
    from browser.highlights import inject_highlight_runtime

    manager, page = _require_browser()
    if page is None:
        # launch/navigate 同刻发起时 launch 可能仍在进行：等它就绪，消除竞态。
        # 未启动且无启动在途时返回 None，保持原有 "not launched" 返回文案。
        page = await _wait_for_launch_ready(manager)
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    result = await _navigate(page, url)
    await _settle_after_click(page)
    await inject_highlight_runtime(page)

    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(url, title)
    manager.record_action("navigate", url)

    if "成功" in result or "Navigated" in result:
        manager.reset_nav_timeout_count()
        manager.reset_element_failures()
        await manager.detect_takeover()
    else:
        # 兜底：认证/网络等失败持续 3 次时直接触发人工接管（Layer 4）。
        manager.record_nav_timeout()

    return result


@db_tool(name="browser_get_url", category="browser", timeout=5, sequential=False)
async def browser_get_url(ctx: RunContext[Settings]) -> str:
    from browser.actions import get_url as _get

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    url = _get(page)
    manager.record_action("get_url", url)
    return url


@db_tool(name="browser_go_back", category="browser", timeout=15, sequential=True, defer_loading=True)
async def browser_go_back(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_back as _back

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _back(page)
    await _settle_after_click(page)
    manager.record_action("go_back", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    await manager.detect_takeover()
    return result


@db_tool(name="browser_go_forward", category="browser", timeout=15, sequential=True, defer_loading=True)
async def browser_go_forward(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_forward as _forward

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _forward(page)
    await _settle_after_click(page)
    manager.record_action("go_forward", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    await manager.detect_takeover()
    return result


@db_tool(name="browser_load_state", category="browser", timeout=15, sequential=True, defer_loading=True)
async def browser_load_state(ctx: RunContext[Settings], state: str = "load") -> str:
    from browser.context import wait_for_load_state as _wait

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _wait(page, state)  # type: ignore[arg-type]
    manager.record_action("load_state", state)
    return result
