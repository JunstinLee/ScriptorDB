from __future__ import annotations

from pydantic_ai import RunContext

from browser import get_manager
from config.settings import Settings
from tools.tool_decorators import db_tool


@db_tool(name="browser_launch", category="browser", timeout=30, sequential=True)
async def browser_launch(ctx: RunContext[Settings]) -> str:
    manager = get_manager()
    return await manager.launch()


@db_tool(name="browser_navigate", category="browser", timeout=30, sequential=True)
async def browser_navigate(ctx: RunContext[Settings], url: str) -> str:
    from browser.context import navigate as _navigate

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _navigate(page, url)


@db_tool(name="browser_get_text", category="browser", timeout=15, sequential=True)
async def browser_get_text(ctx: RunContext[Settings]) -> str:
    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    title = await page.title()
    text = await page.inner_text("body")
    return f"# {title}\n\n{text}"


@db_tool(name="browser_load_state", category="browser", timeout=15, sequential=True)
async def browser_load_state(ctx: RunContext[Settings], state: str = "load") -> str:
    from browser.context import wait_for_load_state as _wait

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _wait(page, state)  # type: ignore[arg-type]


@db_tool(name="browser_evaluate", category="browser", timeout=15, sequential=False)
async def browser_evaluate(ctx: RunContext[Settings], js: str) -> str:
    from browser.runtime import evaluate as _eval

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _eval(page, js)


@db_tool(name="browser_query", category="browser", timeout=10, sequential=False)
async def browser_query(
    ctx: RunContext[Settings],
    selector: str,
    attribute: str = "",
    all: bool = False,
) -> str:
    from browser.runtime import get_image_sources, query_attr, query_attr_all, query_text, query_text_all

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    if selector == "img[src]" and attribute == "src" and all:
        return await get_image_sources(page)

    if attribute:
        if all:
            return await query_attr_all(page, selector, attribute)
        return await query_attr(page, selector, attribute)

    if all:
        return await query_text_all(page, selector)
    return await query_text(page, selector)


@db_tool(name="browser_scroll", category="browser", timeout=15, sequential=False)
async def browser_scroll(
    ctx: RunContext[Settings],
    to_bottom: bool = True,
    pixels: int = 0,
) -> str:
    from browser.actions import scroll_by, scroll_to_bottom

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    if to_bottom:
        return await scroll_to_bottom(page)
    if pixels == 0:
        return "pixels must be non-zero when to_bottom is False"
    return await scroll_by(page, pixels)


@db_tool(name="browser_screenshot", category="browser", timeout=15, sequential=False)
async def browser_screenshot(ctx: RunContext[Settings], path: str = "") -> str:
    from browser.actions import screenshot as _screenshot

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."

    return await _screenshot(page, path if path else None)


@db_tool(name="browser_wait_for_selector", category="browser", timeout=15, sequential=True)
async def browser_wait_for_selector(
    ctx: RunContext[Settings],
    selector: str,
    state: str = "visible",
) -> str:
    from browser.context import wait_for_selector as _wait

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _wait(page, selector, state)  # type: ignore[arg-type]


@db_tool(name="browser_click", category="browser", timeout=15, sequential=True)
async def browser_click(ctx: RunContext[Settings], selector: str) -> str:
    from browser.actions import click as _click

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _click(page, selector)


@db_tool(name="browser_fill", category="browser", timeout=15, sequential=True)
async def browser_fill(ctx: RunContext[Settings], selector: str, text: str) -> str:
    from browser.actions import fill as _fill

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _fill(page, selector, text)


@db_tool(name="browser_press_key", category="browser", timeout=15, sequential=True)
async def browser_press_key(ctx: RunContext[Settings], key: str) -> str:
    from browser.actions import press_key as _press

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _press(page, key)


@db_tool(name="browser_get_cookies", category="browser", timeout=10, sequential=False)
async def browser_get_cookies(ctx: RunContext[Settings]) -> str:
    from browser.context import get_cookies as _get

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _get(page)


@db_tool(name="browser_set_cookies", category="browser", timeout=15, sequential=True)
async def browser_set_cookies(ctx: RunContext[Settings], cookies_json: str) -> str:
    from browser.context import set_cookies as _set

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _set(page, cookies_json)


@db_tool(name="browser_clear_cookies", category="browser", timeout=10, sequential=True)
async def browser_clear_cookies(ctx: RunContext[Settings]) -> str:
    from browser.context import clear_cookies as _clear

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _clear(page)


@db_tool(name="browser_get_url", category="browser", timeout=5, sequential=False)
async def browser_get_url(ctx: RunContext[Settings]) -> str:
    from browser.actions import get_url as _get

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return _get(page)


@db_tool(name="browser_go_back", category="browser", timeout=15, sequential=True)
async def browser_go_back(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_back as _back

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _back(page)


@db_tool(name="browser_go_forward", category="browser", timeout=15, sequential=True)
async def browser_go_forward(ctx: RunContext[Settings]) -> str:
    from browser.actions import go_forward as _forward

    manager = get_manager()
    page = manager.page()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    return await _forward(page)
