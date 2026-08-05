from __future__ import annotations

from playwright.async_api import BrowserContext, Page

from logging_setup import get_logger

logger = get_logger("browser.tabs")


class TabManager:
    """Tracks every page opened in the browser context and manages the active tab.

    Decoupled from BrowserManager's single-page model: the manager delegates tab
    bookkeeping here without rewriting its lifecycle logic.
    """

    def __init__(self) -> None:
        self._context: BrowserContext | None = None
        self._tabs: list[Page] = []
        self._active: int = 0

    def attach(self, context: BrowserContext, initial_page: Page) -> None:
        self._context = context
        self._tabs = []
        self._active = 0
        self._context.on("page", self._on_page_opened)
        self._track(initial_page)

    def detach(self) -> None:
        self._context = None
        self._tabs = []
        self._active = 0

    def _on_page_opened(self, page: Page) -> None:
        self._track(page)
        logger.info(f"new tab opened url={page.url} total_tabs={len(self._tabs)}")

    def _track(self, page: Page) -> None:
        if page in self._tabs:
            return
        self._tabs.append(page)
        page.on("close", self._on_page_closed)

    def _on_page_closed(self, page: Page) -> None:
        if page in self._tabs:
            self._tabs.remove(page)
            if self._active >= len(self._tabs):
                self._active = max(0, len(self._tabs) - 1)
            logger.info(f"tab closed url={page.url} total_tabs={len(self._tabs)}")

    def pages(self) -> list[Page]:
        return list(self._tabs)

    def active_page(self) -> Page | None:
        if not self._tabs:
            return None
        if self._active >= len(self._tabs):
            self._active = len(self._tabs) - 1
        return self._tabs[self._active]

    def switch_tab(self, index: int) -> Page | None:
        if not self._tabs:
            return None
        if index < 0 or index >= len(self._tabs):
            raise IndexError(f"Tab index {index} out of range (0-{len(self._tabs) - 1})")
        self._active = index
        return self._tabs[index]

    async def close_tab(self, index: int) -> str:
        if not self._tabs:
            return "No tabs open"
        if index < 0 or index >= len(self._tabs):
            return f"Tab index {index} out of range (0-{len(self._tabs) - 1})"
        page = self._tabs.pop(index)
        if self._active >= len(self._tabs):
            self._active = max(0, len(self._tabs) - 1)
        try:
            await page.close()
        except Exception as e:
            return f"Failed to close tab {index}: {e}"
        logger.info(f"closed tab {index} via close_tab total_tabs={len(self._tabs)}")
        return f"Closed tab {index}"


__all__ = ["TabManager"]
