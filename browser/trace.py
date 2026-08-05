from __future__ import annotations

from playwright.async_api import Page

from logging_setup import get_logger

logger = get_logger("browser.trace")


class ClickTracer:
    """Records click-driven navigation provenance (pre-click href -> final URL).

    Decoupled from the click tool: the tracer owns the capture logic, while the
    tool wires it in. Nothing here depends on BrowserManager.
    """

    def __init__(self) -> None:
        self._pre_click: dict | None = None

    def reset(self) -> None:
        self._pre_click = None

    async def record_pre_click(self, page: Page, selector: str) -> dict | None:
        try:
            info = await page.evaluate(
                """(selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    const href = el.getAttribute('href');
                    let abs = null;
                    if (href) {
                        try { abs = new URL(href, document.baseURI).href; } catch (e) { abs = null; }
                    }
                    return {
                        selector: selector,
                        href: href,
                        url: abs,
                        text: (el.innerText || '').trim().slice(0, 200),
                        target: el.getAttribute('target') || '',
                        new_tab: el.target === '_blank',
                    };
                }""",
                selector,
            )
        except Exception as e:
            logger.warning(f"trace pre-click failed selector={selector} error={e}")
            info = None
        if not isinstance(info, dict):
            info = None
        self._pre_click = info
        return info

    async def record_post_nav(self, page: Page) -> dict:
        try:
            url = page.url
        except Exception:
            url = ""
        try:
            title = await page.title()
        except Exception:
            title = ""
        status = None
        try:
            resp = getattr(page, "last_response", None)
            if resp is not None:
                status = getattr(resp, "status", None)
        except Exception:
            pass
        trace = {
            "pre_click": self._pre_click,
            "final_url": url,
            "title": title,
            "status_code": status,
        }
        self._pre_click = None
        return trace


__all__ = ["ClickTracer"]
