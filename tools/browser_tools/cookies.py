from __future__ import annotations

from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.cookies")


@db_tool(name="browser_get_cookies", category="browser", timeout=10, sequential=False)
async def browser_get_cookies(ctx: RunContext[Settings]) -> str:
    from browser.context import get_cookies as _get

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _get(page)
    manager.record_action("get_cookies", result[:50])
    return result


@db_tool(name="browser_set_cookies", category="browser", timeout=15, sequential=True)
async def browser_set_cookies(ctx: RunContext[Settings], cookies_json: str) -> str:
    from browser.context import set_cookies as _set

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _set(page, cookies_json)
    try:
        import json

        cookies = json.loads(cookies_json)
        count = len(cookies) if isinstance(cookies, list) else 1
    except Exception:
        count = 0
    manager.record_action("set_cookies", f"{count} cookies")
    return result


@db_tool(name="browser_clear_cookies", category="browser", timeout=10, sequential=True)
async def browser_clear_cookies(ctx: RunContext[Settings]) -> str:
    from browser.context import clear_cookies as _clear

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _clear(page)
    manager.record_action("clear_cookies", result)
    return result
