from __future__ import annotations

import json
from typing import Literal

from playwright.async_api import Page

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
LoadState = Literal["domcontentloaded", "load", "networkidle"]
SelectorState = Literal["attached", "detached", "visible", "hidden"]


async def navigate(page: Page, url: str, wait_until: WaitUntil = "domcontentloaded") -> str:
    await page.goto(url, wait_until=wait_until)
    return f"Navigated to {url}"


async def wait_for_load_state(page: Page, state: LoadState = "load") -> str:
    await page.wait_for_load_state(state)
    return f"Page reached load state: {state}"


async def wait_for_selector(
    page: Page,
    selector: str,
    state: SelectorState = "visible",
    timeout: int = 10_000,
) -> str:
    try:
        await page.wait_for_selector(selector, state=state, timeout=timeout)
        return f"Element '{selector}' is now {state}"
    except Exception as e:
        return f"Wait for selector failed: {e}"


async def get_cookies(page: Page) -> str:
    cookies = await page.context.cookies()
    if not cookies:
        return "No cookies found"
    return json.dumps(cookies, ensure_ascii=False, default=str)


async def set_cookies(page: Page, cookies_json: str) -> str:
    try:
        cookies: list[dict] = json.loads(cookies_json)
    except json.JSONDecodeError as e:
        return f"Invalid cookies JSON: {e}"
    try:
        await page.context.add_cookies(cookies)  # type: ignore[arg-type]
        return f"Set {len(cookies)} cookie(s)"
    except Exception as e:
        return f"Set cookies failed: {e}"


async def clear_cookies(page: Page) -> str:
    try:
        await page.context.clear_cookies()
        return "All cookies cleared"
    except Exception as e:
        return f"Clear cookies failed: {e}"

