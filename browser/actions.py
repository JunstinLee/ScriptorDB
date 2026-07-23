from __future__ import annotations

import os
import time

from playwright.async_api import Page


async def scroll_to_bottom(page: Page) -> str:
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(500)
    return "Scrolled to bottom of page"


async def scroll_by(page: Page, pixels: int) -> str:
    await page.evaluate(f"window.scrollBy(0, {pixels})")
    await page.wait_for_timeout(300)
    return f"Scrolled by {pixels}px"


async def screenshot(page: Page, path: str | None = None) -> str:
    if path is None:
        path = f"outputs/browser/screenshot_{int(time.time())}.png"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await page.screenshot(path=path, full_page=True)
        return f"Screenshot saved to {path}"
    except Exception as e:
        return f"Screenshot failed: {e}"
