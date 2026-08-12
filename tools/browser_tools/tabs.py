from __future__ import annotations

from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.tabs")


@db_tool(name="browser_get_tabs", category="browser", timeout=10, sequential=False)
async def browser_get_tabs(ctx: RunContext[Settings]) -> str:
    manager, _ = _require_browser()
    if manager.page() is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    tabs = manager.tabs.pages()
    if not tabs:
        return "No tabs open"
    active = manager.tabs.active_page()
    lines = []
    for i, tab in enumerate(tabs):
        parts = [f"[{i}]"]
        if tab is active:
            parts.append("ACTIVE")
        parts.append(tab.url)
        try:
            title = await tab.title()
        except Exception:
            title = ""
        if title:
            parts.append(title)
        lines.append(" ".join(parts))
    manager.record_action("get_tabs", f"{len(tabs)} tabs")
    return "\n".join(lines)


@db_tool(name="browser_switch_tab", category="browser", timeout=10, sequential=True)
async def browser_switch_tab(ctx: RunContext[Settings], index: int) -> str:
    manager, _ = _require_browser()
    if not manager.tabs.pages():
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    try:
        page = manager.tabs.switch_tab(index)
    except IndexError as e:
        return str(e)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_action("switch_tab", f"index={index} url={page.url}")
    return f"Switched to tab {index}: {page.url} {title}".strip()
