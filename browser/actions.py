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


async def click(page: Page, selector: str) -> str:
    try:
        await page.click(selector)
        return f"Clicked element: {selector}"
    except Exception as e:
        return f"Click failed: {e}"


async def fill(page: Page, selector: str, text: str) -> str:
    try:
        await page.fill(selector, text)
        return f"Filled '{selector}' with: {text}"
    except Exception as e:
        return f"Fill failed: {e}"


async def press_key(page: Page, key: str) -> str:
    try:
        await page.keyboard.press(key)
        return f"Pressed key: {key}"
    except Exception as e:
        return f"Press key failed: {e}"


async def screenshot(page: Page, path: str | None = None) -> str:
    if path is None:
        path = f"outputs/browser/screenshot_{int(time.time())}.png"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await page.screenshot(path=path, full_page=True)
        return f"Screenshot saved to {path}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def get_url(page: Page) -> str:
    return page.url


async def go_back(page: Page) -> str:
    try:
        await page.go_back()
        return f"Navigated back. Current URL: {page.url}"
    except Exception as e:
        return f"Go back failed: {e}"


async def go_forward(page: Page) -> str:
    try:
        await page.go_forward()
        return f"Navigated forward. Current URL: {page.url}"
    except Exception as e:
        return f"Go forward failed: {e}"
