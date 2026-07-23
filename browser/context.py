from __future__ import annotations

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



