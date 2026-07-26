from __future__ import annotations

from browser import get_manager
from config.settings import Settings
from pydantic_ai import RunContext
from tools.tool_decorators import db_tool


def _require_browser() -> tuple:
    manager = get_manager()
    return manager, manager.page()


@db_tool(name="browser_launch", category="browser", timeout=30, sequential=True)
async def browser_launch(ctx: RunContext[Settings]) -> str:
    manager = get_manager()
    result = await manager.launch()
    manager.record_action("launch", result)
    return result


@db_tool(name="browser_navigate", category="browser", timeout=30, sequential=True)
async def browser_navigate(ctx: RunContext[Settings], url: str) -> str:
    from browser.context import navigate as _navigate

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    result = await _navigate(page, url)

    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(url, title)
    manager.record_action("navigate", url)

    return result


@db_tool(name="browser_get_text", category="browser", timeout=15, sequential=True)
async def browser_get_text(ctx: RunContext[Settings]) -> str:
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    title = await page.title()
    text = await page.inner_text("body")
    result = f"# {title}\n\n{text}"
    manager.record_action("get_text", f"Retrieved {len(result)} chars")
    return result


@db_tool(name="browser_load_state", category="browser", timeout=15, sequential=True)
async def browser_load_state(ctx: RunContext[Settings], state: str = "load") -> str:
    from browser.context import wait_for_load_state as _wait

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _wait(page, state)  # type: ignore[arg-type]
    manager.record_action("load_state", state)
    return result


@db_tool(name="browser_evaluate", category="browser", timeout=15, sequential=False)
async def browser_evaluate(ctx: RunContext[Settings], js: str) -> str:
    from browser.runtime import evaluate as _eval

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _eval(page, js)
    manager.record_action("evaluate", js[:50] + "..." if len(js) > 50 else js)
    return result


@db_tool(name="browser_query", category="browser", timeout=10, sequential=False)
async def browser_query(
    ctx: RunContext[Settings],
    selector: str,
    attribute: str = "",
    all: bool = False,
) -> str:
    from browser.runtime import get_image_sources, query_attr, query_attr_all, query_text, query_text_all

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    if selector == "img[src]" and attribute == "src" and all:
        result = await get_image_sources(page)
        manager.record_action("query", selector)
        return result

    if attribute:
        if all:
            result = await query_attr_all(page, selector, attribute)
        else:
            result = await query_attr(page, selector, attribute)
    elif all:
        result = await query_text_all(page, selector)
    else:
        result = await query_text(page, selector)

    manager.record_action("query", selector)
    return result


@db_tool(name="browser_scroll", category="browser", timeout=15, sequential=False)
async def browser_scroll(
    ctx: RunContext[Settings],
    to_bottom: bool = True,
    pixels: int = 0,
) -> str:
    from browser.actions import scroll_by, scroll_to_bottom

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    if to_bottom:
        result = await scroll_to_bottom(page)
    elif pixels == 0:
        return "pixels must be non-zero when to_bottom is False"
    else:
        result = await scroll_by(page, pixels)

    manager.record_action("scroll", "bottom" if to_bottom else f"{pixels}px")
    return result


@db_tool(name="browser_screenshot", category="browser", timeout=15, sequential=False)
async def browser_screenshot(ctx: RunContext[Settings], path: str = "") -> str:
    from browser.actions import screenshot as _screenshot

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    result = await _screenshot(page, path if path else None)

    if "Screenshot saved" in result:
        actual_path = result.replace("Screenshot saved to ", "").strip()
        manager.record_screenshot(actual_path)

    manager.record_action("screenshot", result, success="Screenshot saved" in result)

    return result


@db_tool(name="browser_wait_for_selector", category="browser", timeout=15, sequential=True)
async def browser_wait_for_selector(
    ctx: RunContext[Settings],
    selector: str,
    state: str = "visible",
) -> str:
    from browser.context import wait_for_selector as _wait

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _wait(page, selector, state)  # type: ignore[arg-type]
    manager.record_action("wait_for_selector", selector)
    return result


@db_tool(name="browser_click", category="browser", timeout=15, sequential=True)
async def browser_click(ctx: RunContext[Settings], selector: str) -> str:
    from browser.actions import click as _click

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _click(page, selector)
    manager.record_action("click", selector)
    return result


@db_tool(name="browser_fill", category="browser", timeout=15, sequential=True)
async def browser_fill(ctx: RunContext[Settings], selector: str, text: str) -> str:
    from browser.actions import fill as _fill

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _fill(page, selector, text)
    manager.record_action("fill", selector)
    return result


@db_tool(name="browser_press_key", category="browser", timeout=15, sequential=True)
async def browser_press_key(ctx: RunContext[Settings], key: str) -> str:
    from browser.actions import press_key as _press

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _press(page, key)
    manager.record_action("press_key", key)
    return result


@db_tool(name="browser_get_cookies", category="browser", timeout=10, sequential=False)
async def browser_get_cookies(ctx: RunContext[Settings]) -> str:
    from browser.context import get_cookies as _get

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _get(page)
    manager.record_action("get_cookies", result[:50])
    return result


@db_tool(name="browser_set_cookies", category="browser", timeout=15, sequential=True)
async def browser_set_cookies(ctx: RunContext[Settings], cookies_json: str) -> str:
    from browser.context import set_cookies as _set

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
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
    result = await _clear(page)
    manager.record_action("clear_cookies", result)
    return result


@db_tool(name="browser_get_url", category="browser", timeout=5, sequential=False)
async def browser_get_url(ctx: RunContext[Settings]) -> str:
    from browser.actions import get_url as _get

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    url = _get(page)
    manager.record_action("get_url", url)
    return url


@db_tool(name="browser_go_back", category="browser", timeout=15, sequential=True)
async def browser_go_back(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_back as _back

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _back(page)
    manager.record_action("go_back", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    return result


@db_tool(name="browser_go_forward", category="browser", timeout=15, sequential=True)
async def browser_go_forward(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_forward as _forward

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    result = await _forward(page)
    manager.record_action("go_forward", result)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_navigate(page.url, title)
    return result
