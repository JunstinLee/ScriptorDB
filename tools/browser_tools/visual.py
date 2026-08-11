from __future__ import annotations

from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.visual")


@db_tool(name="browser_screenshot", category="browser", timeout=15, sequential=False)
async def browser_screenshot(ctx: RunContext[Settings], path: str = "") -> str:
    from browser.actions import screenshot as _screenshot

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    result = await _screenshot(page, path if path else None)

    if "Screenshot saved" in result:
        actual_path = result.replace("Screenshot saved to ", "").strip()
        manager.record_screenshot(actual_path)

    manager.record_action("screenshot", result, success="Screenshot saved" in result)

    return result
