from __future__ import annotations

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

# 点击前元素不可见时的有界重试预算：面板动画 / 列表重建常在此期间完成，
# 给足窗口即可把大量「暂时隐藏」从失败里救回来。
_VISIBLE_RETRY_MS = 2000


async def scroll_to_bottom(page: Page) -> str:
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(500)
    return "Scrolled to bottom of page"


async def scroll_by(page: Page, pixels: int) -> str:
    await page.evaluate(f"window.scrollBy(0, {pixels})")
    await page.wait_for_timeout(300)
    return f"Scrolled by {pixels}px"


async def click(page: Page, selector: str, timeout: int = 30_000) -> str:
    try:
        element = await page.query_selector(selector)
        if element is None:
            return f"Click failed: element not found: {selector}"
        if not await element.is_visible():
            # 元素可能只是暂时隐藏（面板动画 / 列表重建）：先给一次有界的可见性
            # 等待，再重新取句柄复核，避免把可恢复的过渡态直接判成失败。
            try:
                await page.wait_for_selector(
                    selector, state="visible", timeout=_VISIBLE_RETRY_MS,
                )
            except Exception:
                pass
            element = await page.query_selector(selector)
            if element is None or not await element.is_visible():
                return f"Click failed: element is not visible: {selector}"
        if not await element.is_enabled():
            return f"Click failed: element is disabled: {selector}"
        await page.click(selector, timeout=timeout)
        return f"Clicked element: {selector}"
    except PlaywrightTimeoutError:
        return (
            f"Click failed: timed out after {timeout}ms — element not actionable "
            f"(covered by another element, unstable, or detached): {selector}"
        )
    except Exception as e:
        return f"Click failed: {selector} ({type(e).__name__}: {e})"


async def fill(page: Page, selector: str, text: str, timeout: int = 30_000) -> str:
    try:
        element = await page.query_selector(selector)
        if element is not None and not await element.is_editable():
            return f"Fill failed: element is not editable (readonly/disabled): {selector}"
        await page.fill(selector, text, timeout=timeout)
        return f"Filled {selector}"
    except Exception as e:
        return f"Fill failed: {e}"


async def select_option(page: Page, selector: str, value: str = "", label: str = "", timeout: int = 30_000) -> str:
    try:
        if label:
            await page.select_option(selector, label=label, timeout=timeout)
            return f"Selected option '{label}' for {selector}"
        await page.select_option(selector, value=value, timeout=timeout)
        return f"Selected option '{value}' for {selector}"
    except Exception as e:
        return f"Select failed: {e}"


async def press_key(page: Page, key: str) -> str:
    try:
        await page.keyboard.press(key)
        return f"Pressed key: {key}"
    except Exception as e:
        return f"Press key failed: {e}"


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
