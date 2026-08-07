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
