from __future__ import annotations

from datetime import datetime, timezone

from playwright.async_api import Browser, BrowserContext, Page, Playwright


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        self._history: list[dict[str, str]] = []
        self._actions: list[dict] = []
        self._last_screenshot: str | None = None
        self._launched_at: float | None = None

    def record_navigate(self, url: str, title: str = "") -> None:
        self._history.append({
            "url": url,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def record_action(self, tool: str, detail: str, success: bool = True) -> None:
        self._actions.append({
            "tool": tool,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success
        })

    def record_screenshot(self, path: str) -> None:
        self._last_screenshot = path

    def reset_state(self) -> None:
        self._history.clear()
        self._actions.clear()
        self._last_screenshot = None
        self._launched_at = None

    async def get_state(self) -> dict:
        launched = self.is_launched()
        page = self.page()

        url = None
        title = None
        if launched and page is not None:
            try:
                url = page.url
            except Exception:
                url = None
            try:
                title = await page.title()
            except Exception:
                title = None

        return {
            "launched": launched,
            "url": url,
            "title": title,
            "screenshot_available": self._last_screenshot is not None,
            "screenshot_path": self._last_screenshot,
            "launched_at": self._launched_at,
            "actions": list(self._actions),
            "history": list(self._history),
        }

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

        self._launched_at = datetime.now(timezone.utc).timestamp()
        self.reset_state()

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
        self.reset_state()
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
