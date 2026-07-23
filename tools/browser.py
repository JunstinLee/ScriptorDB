from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Page, Playwright
from pydantic_ai import RunContext

from config.settings import Settings
from tools.tool_decorators import db_tool

_playwright: Playwright | None = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None


def _reset_browser() -> None:
    global _playwright, _browser, _context, _page
    _playwright = None
    _browser = None
    _context = None
    _page = None


@db_tool(name="browser_launch", category="browser", timeout=30, sequential=True)
async def browser_launch(ctx: RunContext[Settings]) -> str:
    global _playwright, _browser, _context, _page
    if _browser is not None:
        return "Browser already launched"

    try:
        from playwright.async_api import async_playwright as ap
    except ImportError:
        return "Playwright is not installed. Run: pip install playwright && playwright install chromium"

    _playwright = await ap().start()
    _browser = await _playwright.chromium.launch(headless=True)
    _context = await _browser.new_context()
    _page = await _context.new_page()
    return "Browser launched successfully in headless mode"


@db_tool(name="browser_navigate", category="browser", timeout=30, sequential=True)
async def browser_navigate(ctx: RunContext[Settings], url: str) -> str:
    global _page
    if _page is None:
        return "Browser not launched. Please call browser_launch first."

    await _page.goto(url, wait_until="domcontentloaded")
    return f"Navigated to {url}"


@db_tool(name="browser_get_text", category="browser", timeout=15, sequential=True)
async def browser_get_text(ctx: RunContext[Settings]) -> str:
    global _page
    if _page is None:
        return "Browser not launched. Please call browser_launch first."

    title = await _page.title()
    text = await _page.inner_text("body")
    return f"# {title}\n\n{text}"
