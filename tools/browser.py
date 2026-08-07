from __future__ import annotations

from browser import get_manager
from browser.takeover import HumanTakeoverState
from logging_setup import get_logger

logger = get_logger("tools.browser")

_NEXT_SELECTOR_CANDIDATES = (
    '[rel="next"]',
    ".pager-next",
    ".next",
    ".pagination-next",
    'button.next',
    '[aria-label*="next" i]',
)


def _require_browser() -> tuple:
    manager = get_manager()
    manager.cancel_idle_close()
    return manager, manager.page()


def _check_blocked(manager) -> str | None:
    state = manager.takeover.state
    if state in (HumanTakeoverState.HUMAN_CONTROL, HumanTakeoverState.WAITING_HUMAN, HumanTakeoverState.DETECTED):
        logger.warning(f"[BLOCKED] browser tool blocked, takeover_state={state.value}")
        return f"Browser interaction blocked: takeover state is '{state.value}'. Agent cannot control the browser until human takeover is completed or cancelled."
    return None


async def _click_next(page, selector: str) -> bool:
    """Click the site-pagination "next" button; return False if unavailable."""
    sel = selector
    if not sel:
        for candidate in _NEXT_SELECTOR_CANDIDATES:
            if await page.query_selector(candidate) is not None:
                sel = candidate
                break
        if not sel:
            return False
    element = await page.query_selector(sel)
    if element is None:
        return False
    try:
        if await element.get_attribute("disabled") is not None:
            return False
        aria = await element.get_attribute("aria-disabled")
        if aria and str(aria).lower() == "true":
            return False
        await element.click()
        return True
    except Exception:
        try:
            clicked = await page.evaluate(
                "(s) => { const b = document.querySelector(s); if (b) { b.click(); return true; } return false; }",
                sel,
            )
            return bool(clicked)
        except Exception:
            return False


async def _settle_after_click(page) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    await page.wait_for_timeout(500)


# Facade re-exports: all browser tools live in tools/browser_tools/*. These imports
# are placed after the shared helpers above so the submodules can import them without
# circular-import issues.
from tools.browser_tools.cookies import (  # noqa: E402
    browser_clear_cookies,
    browser_get_cookies,
    browser_set_cookies,
)
from tools.browser_tools.dom import (  # noqa: E402
    browser_click,
    browser_evaluate,
    browser_fill,
    browser_get_text,
    browser_press_key,
    browser_query,
    browser_scroll,
    browser_wait_for_selector,
)
from tools.browser_tools.inspect import browser_inspect_structure  # noqa: E402
from tools.browser_tools.links import browser_extract_links  # noqa: E402
from tools.browser_tools.navigation import (  # noqa: E402
    browser_get_url,
    browser_go_back,
    browser_go_forward,
    browser_launch,
    browser_load_state,
    browser_navigate,
)
from tools.browser_tools.table import browser_extract_table  # noqa: E402
from tools.browser_tools.tabs import browser_get_tabs, browser_switch_tab  # noqa: E402
from tools.browser_tools.visual import browser_screenshot  # noqa: E402

__all__ = [
    "browser_clear_cookies",
    "browser_click",
    "browser_evaluate",
    "browser_extract_links",
    "browser_extract_table",
    "browser_fill",
    "browser_get_cookies",
    "browser_get_tabs",
    "browser_get_text",
    "browser_get_url",
    "browser_go_back",
    "browser_go_forward",
    "browser_inspect_structure",
    "browser_launch",
    "browser_load_state",
    "browser_navigate",
    "browser_press_key",
    "browser_query",
    "browser_screenshot",
    "browser_scroll",
    "browser_set_cookies",
    "browser_switch_tab",
    "browser_wait_for_selector",
]
