from __future__ import annotations

from browser import get_manager
from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.navigation")


@db_tool(name="browser_launch", category="browser", timeout=30, sequential=True)
async def browser_launch(ctx: RunContext[Settings]) -> str:
    manager = get_manager()
    manager.cancel_idle_close()
    logger.info("browser_launch called")
    result = await manager.launch()
    manager.record_action("launch", result)
    return result


@db_tool(name="browser_navigate", category="browser", timeout=30, sequential=True)
async def browser_navigate(ctx: RunContext[Settings], url: str) -> str:
    from browser.context import navigate as _navigate
    from browser.highlights import inject_highlight_runtime

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    logger.info(f"browser_navigate url={url} takeover_state={manager.takeover.state.value}")
    result = await _navigate(page, url)
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
        logger.info(f"browser_navigate detect_takeover result takeover_state={manager.takeover.state.value}")

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


@db_tool(name="browser_go_back", category="browser", timeout=15, sequential=True)
async def browser_go_back(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_back as _back

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _back(page)
    manager.record_action("go_back", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    await manager.detect_takeover()
    logger.info(f"browser_go_back detect_takeover result takeover_state={manager.takeover.state.value}")
    return result


@db_tool(name="browser_go_forward", category="browser", timeout=15, sequential=True)
async def browser_go_forward(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_forward as _forward

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _forward(page)
    manager.record_action("go_forward", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    await manager.detect_takeover()
    logger.info(f"browser_go_forward detect_takeover result takeover_state={manager.takeover.state.value}")
    return result


@db_tool(name="browser_load_state", category="browser", timeout=15, sequential=True)
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
