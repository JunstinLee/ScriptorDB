from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Page, Playwright


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def launch(self, headless: bool = True) -> str:
        if self._browser is not None:
            return "Browser already launched"

        try:
            from playwright.async_api import async_playwright as ap
        except ImportError:
            return "Playwright is not installed. Run: pip install playwright && playwright install chromium"

        try:
            self._playwright = await ap().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        except Exception as e:
            self.reset()
            return f"Browser launch failed: {e}"

        mode = "headless" if headless else "visible"
        return f"Browser launched successfully in {mode} mode"

    async def close(self) -> str:
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
        return "Browser closed"

    def is_launched(self) -> bool:
        return self._browser is not None

    def page(self) -> Page | None:
        return self._page

    def reset(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
