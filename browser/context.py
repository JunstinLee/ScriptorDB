from __future__ import annotations

import json
from typing import Literal

from playwright.async_api import Page

from browser.login_state import netloc_of
from core.logging_setup import get_logger

logger = get_logger("browser.context")

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
LoadState = Literal["domcontentloaded", "load", "networkidle"]
SelectorState = Literal["attached", "detached", "visible", "hidden"]


async def navigate(page: Page, url: str, wait_until: WaitUntil = "domcontentloaded") -> str:
    logger.info(f"page.goto url={url}")
    try:
        # timeout=25s < 工具装饰器 30s 超时窗口：goto 先自行超时抛出，
        # 由下方 except 接住返回失败字符串。若依赖 playwright 默认 30s，
        # 会与装饰器的 wait_for 同时到点，底层任务泄漏（Future never
        # retrieved）并残留并发导航，导致后续 evaluate 撞上被销毁的上下文。
        await page.goto(url, wait_until=wait_until, timeout=25_000)
        try:
            from browser import get_manager
            await get_manager().notify_screencast_restart()
        except Exception:
            pass
        return f"Navigated to {url}"
    except Exception as e:
        if "ERR_INVALID_AUTH" in str(e):
            try:
                from browser import get_manager
                get_manager().record_auth_challenge(netloc_of(url))
            except Exception:
                pass
        logger.error(f"page.goto failed url={url} error={e}")
        return f"Navigation failed: {e}"


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

