from __future__ import annotations

import inspect
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, Playwright

from browser.takeover import HumanTakeoverManager, HumanTakeoverState, detect_human_needed, detect_timeout_trigger, detect_element_failure_trigger
from logging_setup import get_logger

logger = get_logger("browser.manager")

SCREENSHOT_TTL = 30


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._launching = False

        self._history: list[dict[str, str]] = []
        self._actions: list[dict] = []
        self._last_screenshot: str | None = None
        self._last_screenshot_time: float = 0
        self._launched_at: float | None = None
        self._takeover = HumanTakeoverManager()
        self._nav_timeout_count = 0
        self._element_failure_count: dict[str, int] = {}
        self._screencast_connection: object | None = None

    @property
    def takeover(self) -> HumanTakeoverManager:
        return self._takeover

    def set_screencast_connection(self, conn: object | None) -> None:
        self._screencast_connection = conn

    def is_screencast_connection(self, conn: object) -> bool:
        return self._screencast_connection is conn

    def clear_screencast_connection(self, conn: object) -> None:
        if self._screencast_connection is conn:
            self._screencast_connection = None

    async def notify_screencast_restart(self) -> None:
        if self._screencast_connection and hasattr(self._screencast_connection, "ensure_screencast_active"):
            await self._screencast_connection.ensure_screencast_active()  # type: ignore[union-attr]

    def record_navigate(self, url: str, title: str = "") -> None:
        self._history.append({
            "url": url,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def record_action(self, tool: str, detail: str, success: bool = True,
                      selector: str = "", coords: dict | None = None,
                      screenshot_path: str = "") -> None:
        self._actions.append({
            "tool": tool,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "selector": selector,
            "coords": coords or {},
            "screenshot_path": screenshot_path,
        })
        if len(self._actions) > 200:
            self._actions = self._actions[-200:]

    def record_screenshot(self, path: str) -> None:
        self._last_screenshot = path
        self._last_screenshot_time = time.monotonic()

    def reset_state(self) -> None:
        self._history.clear()
        self._actions.clear()
        self._last_screenshot = None
        self._last_screenshot_time = 0
        self._launched_at = None

    async def get_state(self) -> dict:
        launched = self.is_launched()
        page = self.page()

        url = None
        title = None
        if launched and page is not None:
            try:
                url = page.url
                title = await page.title()
            except Exception:
                self._clear_browser_refs(log_warning=True)
                launched = False

        return {
            "launched": launched,
            "url": url,
            "title": title,
            "screenshot_available": (
                self._last_screenshot is not None
                and (time.monotonic() - self._last_screenshot_time) < SCREENSHOT_TTL
            ),
            "screenshot_path": self._last_screenshot,
            "launched_at": self._launched_at,
            "actions": list(self._actions),
            "history": list(self._history),
        }

    async def launch(
        self,
        headless: bool = True,
        storage_state: dict | Path | None = None,
        proxy: dict | None = None,
    ) -> str:
        if self._launching:
            return "Browser launch already in progress"
        if self._browser is not None and self._context is None and self._page is None:
            return "Browser already launched"
        if self.is_launched():
            return "Browser already launched"

        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs()

        try:
            from playwright.async_api import async_playwright as ap
        except ImportError:
            return "Playwright is not installed. Run: pip install playwright && playwright install chromium"

        self._launching = True
        try:
            self._playwright = await ap().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            browser_event: object = self._browser.on("disconnected", self._on_browser_disconnected)
            if inspect.isawaitable(browser_event):
                await browser_event
            context_options: dict = {"viewport": {"width": 1280, "height": 720}}
            if storage_state:
                if isinstance(storage_state, Path):
                    context_options["storage_state"] = str(storage_state)
                else:
                    context_options["storage_state"] = storage_state
            self._context = await self._browser.new_context(**context_options)
            self._page = await self._context.new_page()
            page_event: object = self._page.on("close", self._on_page_closed)
            if inspect.isawaitable(page_event):
                await page_event
        except Exception as e:
            self.reset()
            return f"Browser launch failed: {e}"
        finally:
            self._launching = False

        self.reset_state()
        self._launched_at = datetime.now(timezone.utc).timestamp()

        mode = "headless" if headless else "visible"
        logger.info(f"browser launched headless=False")
        return f"Browser launched successfully in visible mode"

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
            self._clear_browser_refs()
        self.reset_state()
        logger.info("browser closed")
        return "Browser closed"

    async def show_window(self):
        if not self.is_launched() or not self._context:
            return
        try:
            pages = self._context.pages
            if pages:
                await pages[0].bring_to_front()
        except Exception:
            self._clear_browser_refs(log_warning=True)

    async def load_profile(self, name: str, workspace_id: str) -> bool:
        from config.secrets import get_browser_profile
        from browser.profiles import load_profile as _load_profile

        if not self.is_launched():
            storage_state = get_browser_profile(workspace_id, name)
            if not storage_state:
                return False
            await self.launch(storage_state=storage_state)
            return True

        return await _load_profile(self, name, workspace_id)

    def is_launched(self) -> bool:
        if self._launching:
            return False
        if self._browser_is_alive():
            return True
        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs(log_warning=True)
        return False

    def page(self) -> Page | None:
        if self._launching:
            return None
        if self._browser is None and self._context is None and self._playwright is None:
            return self._page
        if self._browser_is_alive():
            return self._page
        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs(log_warning=True)
        return None

    def reset(self) -> None:
        self._clear_browser_refs()
        self._nav_timeout_count = 0
        self._element_failure_count.clear()

    def mark_browser_unavailable(self) -> None:
        self._clear_browser_refs(log_warning=True)

    def _browser_is_alive(self) -> bool:
        if self._browser is None or self._context is None or self._page is None:
            return False
        try:
            return self._browser.is_connected() and not self._page.is_closed()
        except Exception:
            return False

    def _clear_browser_refs(self, log_warning: bool = False) -> None:
        had_browser = any((self._playwright, self._browser, self._context, self._page))
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._launched_at = None
        self._screencast_connection = None
        self._takeover.reset()
        if had_browser and log_warning:
            logger.warning("browser target unavailable; cleared Playwright state")

    def _on_browser_disconnected(self, browser: Browser | None = None) -> None:
        if browser is None or browser is self._browser:
            logger.warning("browser disconnected")
            self._clear_browser_refs()

    def _on_page_closed(self, page: Page | None = None) -> None:
        if page is None or page is self._page:
            logger.warning("browser page closed")
            self._clear_browser_refs()

    async def detect_takeover(self) -> bool:
        if not self.is_launched() or self._page is None:
            return False
        if self._takeover.state != HumanTakeoverState.RUNNING:
            return False
        trigger = await detect_human_needed(self._page)
        if trigger:
            logger.warning(f"takeover detected trigger={trigger.trigger} reason={trigger.reason}")
            return self._takeover.request_takeover(
                reason=trigger.reason,
                trigger=trigger.trigger,
                url=self._page.url,
            )
        return False

    def record_nav_timeout(self):
        self._nav_timeout_count += 1
        logger.warning(f"nav timeout count={self._nav_timeout_count}")
        trigger = detect_timeout_trigger(self._nav_timeout_count)
        if trigger:
            self._takeover.request_takeover(trigger.reason, trigger.trigger)

    def reset_nav_timeout_count(self):
        self._nav_timeout_count = 0

    def record_element_failure(self, selector: str):
        self._element_failure_count[selector] = self._element_failure_count.get(selector, 0) + 1
        count = self._element_failure_count[selector]
        trigger = detect_element_failure_trigger(count)
        if trigger:
            self._takeover.request_takeover(trigger.reason, trigger.trigger)

    def reset_element_failures(self):
        self._element_failure_count.clear()
