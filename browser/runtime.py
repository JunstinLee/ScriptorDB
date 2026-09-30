from __future__ import annotations

import asyncio
import json

from playwright.async_api import Page

from browser import locate_probes
from browser.locate_script import LOCATE_ELEMENTS_JS
from core.logging_setup import get_logger

logger = get_logger("browser.runtime")

# 确认阶段的成本预算。候选数量在 JS 源头就被控制住（族配额 + 共享余量，
# 见 locate_script.LOCATE_ELEMENTS_JS），MAX_CONFIRM_CANDIDATES 是硬上限；
# Python 侧只做最终排序与确认，不再承担「上千 → 60」的截断。
MAX_CONFIRM_CANDIDATES = 60
CONFIRM_CONCURRENCY = 6

# 候选族保底配额：防止单一大族（整页的 div/span）吃光名额。各族先拿固定配额，
# 配额用完不再收同族元素；剩余名额按族轮转分配。`other` 无保底，只能用共享余量。
LOCATE_FAMILY_QUOTAS = {
    "date": 42,
    "nav": 6,
    "input": 10,
    "button": 12,
    "link": 4,
    "other": 0,
}

# 原生具备 disabled 语义的表单控件：只有这些节点才让 is_enabled() 参与一票否决；
# 组件库把交互语义放在 div/span/td 上，is_enabled() 对其无意义。
_FORM_CONTROL_TAGS = {
    "button", "input", "select", "textarea", "option", "optgroup", "fieldset",
}


class InvalidSelectorError(Exception):
    """选择器既不是合法 CSS，也不是 Playwright 引擎选择器。"""


def _is_selector_error(e: Exception) -> bool:
    return isinstance(e, SyntaxError) or "not a valid selector" in str(e)


async def evaluate(page: Page, js: str) -> str:
    try:
        result = await page.evaluate(f"() => {{ return {js} }}")
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return f"JS evaluation error: {e}"


async def query_text(page: Page, selector: str) -> str:
    try:
        element = await page.query_selector(selector)
        if element is None:
            return f"No element found for selector: {selector}"
        return await element.inner_text()
    except Exception as e:
        if _is_selector_error(e):
            raise InvalidSelectorError(str(e)) from e
        return f"Query text error: {e}"


async def query_text_all(page: Page, selector: str) -> str:
    try:
        elements = await page.query_selector_all(selector)
        if not elements:
            return f"No elements found for selector: {selector}"
        results = []
        for i, el in enumerate(elements):
            text = await el.inner_text()
            results.append(f"[{i}] {text}")
        return "\n".join(results)
    except Exception as e:
        if _is_selector_error(e):
            raise InvalidSelectorError(str(e)) from e
        return f"Query text all error: {e}"


async def query_attr(page: Page, selector: str, attr: str) -> str:
    try:
        element = await page.query_selector(selector)
        if element is None:
            return f"No element found for selector: {selector}"
        value = await element.get_attribute(attr)
        return value if value is not None else f"Attribute '{attr}' not found on {selector}"
    except Exception as e:
        if _is_selector_error(e):
            raise InvalidSelectorError(str(e)) from e
        return f"Query attr error: {e}"


async def query_attr_all(page: Page, selector: str, attr: str) -> str:
    try:
        elements = await page.query_selector_all(selector)
        if not elements:
            return f"No elements found for selector: {selector}"
        results = []
        for i, el in enumerate(elements):
            value = await el.get_attribute(attr)
            results.append(f"[{i}] {value if value is not None else '(none)'}")
        return "\n".join(results)
    except Exception as e:
        if _is_selector_error(e):
            raise InvalidSelectorError(str(e)) from e
        return f"Query attr all error: {e}"


async def get_image_sources(page: Page) -> str:
    try:
        sources: list[str] = await page.evaluate("""
            () => {
                const imgs = document.querySelectorAll('img[src]');
                return Array.from(imgs).map(img => img.getAttribute('src'));
            }
        """)
        if not sources:
            return "No images with src found on page"
        return "\n".join(f"[{i}] {src}" for i, src in enumerate(sources))
    except Exception as e:
        return f"Get image sources error: {e}"


def _has_stable_attr(el: dict) -> bool:
    """候选是否由稳定属性定位（id / aria-label / name / data-test*）——预排序用。"""
    selector = el.get("selector") or ""
    return (
        bool(el.get("id"))
        or bool(el.get("ariaLabel"))
        or selector.startswith("#")
        or "data-test" in selector
        or "[name=" in selector
    )


def _candidate_rank(el: dict) -> tuple:
    """预排序键：「活跃覆盖层 > 活跃容器 > 视口 > 其余」，同级再看稳定属性。

    活跃覆盖层（已打开的面板 / 下拉 / 弹层）里的节点最该被保留，排在首位，
    避免被全局 cap 挤到 60 名之外。
    """
    if el.get("overlay") and el.get("containerKey"):
        tier = 0
    elif el.get("containerKey") and el.get("inActive", True):
        tier = 1
    elif el.get("inViewport", False):
        tier = 2
    else:
        tier = 3
    return (
        tier,
        not el.get("inViewport", False),
        not el.get("inActive", True),
        not _has_stable_attr(el),
    )


def _order_candidates(elements: list[dict]) -> list[dict]:
    """最终排序：活跃覆盖层 > 活跃容器 > 视口 > 其余。

    数量已在 JS 源头按族配额 + 共享余量截断，Python 不再做批量剔除，只负责
    让确认顺序把已打开的覆盖层（日期面板 / 下拉）排在前面。末尾的兜底切片是
    防御性的，不应触发；一旦触发说明 JS 限流失效，记 WARNING。
    """
    ordered = sorted(elements, key=_candidate_rank)
    if len(ordered) > MAX_CONFIRM_CANDIDATES:
        logger.warning(
            "locate: JS candidate cap did not hold (%d > %d); truncating defensively",
            len(ordered), MAX_CONFIRM_CANDIDATES,
        )
        ordered = ordered[:MAX_CONFIRM_CANDIDATES]
    logger.info("locate: confirming %d candidates", len(ordered))
    return ordered


async def locate_elements(
    page: Page, text: str = "", role: str = "", scope: str = "visible"
) -> list[dict]:
    """Collect visible, interactive elements into ready-to-reuse selectors.

    Two-layer pipeline: :data:`~browser.locate_script.LOCATE_ELEMENTS_JS` does a
    first-layer layout screening (drops ``display:none`` / ``visibility:hidden`` /
    zero-size nodes and attaches the raw signals ``enabled``/``inViewport``/
    ``receivesEvents``/``rect``/``visibility``/``inActive``), then
    :func:`_confirm_actionable` decides a three-state ``state`` per surviving
    candidate from those signals plus Playwright's own ``is_visible``/``is_enabled``.

    ``state`` is one of:

    - ``"usable"``    — the selector resolves and Playwright confirms visible,
      enabled and actually receiving pointer events; safe to click/fill.
    - ``"blocked"``   — the selector resolves but the element is not operable now;
      ``state_reason`` names why (``hidden`` / ``disabled`` / ``covered`` / ``detached``).
    - ``"unverified"`` — the selector could not be resolved (``query_selector``
      returned ``None`` or raised), so actionability is simply unknown.

    The distinction matters to callers: "known unusable" and "not verified" are no
    longer collapsed into one boolean. ``actionable`` is kept as a derived convenience
    flag (``state == "usable"``); ``enabled`` stays the raw JS layout heuristic.

    Each entry also carries ``{tag, text, role, id, value, ariaLabel, selector,
    semantic, path, receivesEvents, inViewport, inActive, rect, visibility,
    state, state_reason, actionable}`` where ``selector`` can be passed straight back
    to ``browser_click``/``browser_fill``. ``selector`` is built deterministically
    (stable attribute -> aria-label -> unique text -> ``nth-of-type`` CSS path) so the
    same element resolves the same way across repeated locates. ``text`` (substring of
    element text) and ``role`` optionally narrow the result.

    ``path`` (body -> self tag chain), ``ariaLabel`` and ``semantic`` are informational
    only: they are surfaced in this return structure and never gate actionability,
    which stays with the visibility / active-container / interactivity signals. Raises
    nothing; returns ``[]`` on error.

    ``scope`` bounds how wide the scan goes: ``"visible"`` (default) keeps only
    components inside the viewport **and** the current active container so hidden
    sibling panels (ex. the coexisting visible/hidden month-panels of a date picker)
    stay out of the result; ``"container"`` keeps the whole active container even
    when slightly off-viewport; ``"page"`` drops the screening and returns the raw
    DOM matches. Breadth is bounded at the source: the JS layer admits candidates by
    family quota + shared remainder up to :data:`MAX_CONFIRM_CANDIDATES` before any
    layout work runs, so callers can widen the scope but cannot make the pipeline
    examine an unbounded number of nodes.
    """
    scope = (scope or "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"
    try:
        raw = await page.evaluate(
            LOCATE_ELEMENTS_JS,
            {
                "text": text or "",
                "role": role or "",
                "scope": scope,
                "extraSelector": locate_probes.interactive_extra_selector(),
                "overlaySelector": locate_probes.overlay_selector(),
                "classPattern": locate_probes.CLASS_PATTERN,
                "totalCap": MAX_CONFIRM_CANDIDATES,
                "familyQuotas": LOCATE_FAMILY_QUOTAS,
            },
        )
        if not isinstance(raw, list):
            return []
        elements = [d for d in raw if isinstance(d, dict)]
        await _confirm_actionable(page, elements)
        return elements
    except Exception:
        return []


async def _confirm_actionable(page: Page, elements: list[dict]) -> None:
    """Second-layer Playwright confirmation that decides each candidate's ``state``.

    Operability is a three-state, not a boolean: a candidate whose selector resolves
    but is not operable now is ``blocked`` (with a ``state_reason``), while one whose
    selector cannot be resolved at all is ``unverified`` — the two are kept apart so
    downstream output can filter verified elements and still fall back explicitly.

    Cost is bounded two ways so the whole pass fits the tool's 15 s budget: the JS layer
    already capped the pool at :data:`MAX_CONFIRM_CANDIDATES` (family quota + shared
    remainder), and here the candidates are only reordered (active overlay / active
    container / in-viewport first) and then confirmed with :data:`CONFIRM_CONCURRENCY`
    concurrent workers instead of 3 serial round trips per element. ``elements`` is
    reduced in place to the confirmed (and reordered) set.
    """
    candidates = _order_candidates(elements)

    semaphore = asyncio.Semaphore(CONFIRM_CONCURRENCY)

    async def confirm(el: dict) -> None:
        async with semaphore:
            await _confirm_one(page, el)

    await asyncio.gather(*(confirm(el) for el in candidates))
    elements[:] = candidates


async def _confirm_one(page: Page, el: dict) -> None:
    """Resolve one candidate's ``state`` / ``state_reason`` from Playwright."""
    selector = el.get("selector") or ""
    state = "unverified"
    reason = ""
    if selector:
        handle = None
        try:
            handle = await page.query_selector(selector)
        except Exception as e:
            logger.debug(
                "locate: selector %r not parsed (%s)", selector, type(e).__name__,
            )
        if handle is not None:
            try:
                visible = bool(await handle.is_visible())
                enabled = bool(await handle.is_enabled())
            except Exception as e:
                message = str(e).lower()
                if "detach" in message or "not attached" in message:
                    state, reason = "blocked", "detached"
                else:
                    logger.debug(
                        "locate: handle check failed for %r (%s)",
                        selector, type(e).__name__,
                    )
            else:
                # 仅原生表单控件让 is_enabled() 参与一票否决；组件库把交互语义放在
                # div/span/td 上，is_enabled() 对其恒为真且无意义，不应因此被判 blocked。
                tag = (el.get("tag") or "").lower()
                strict_enabled = enabled or tag not in _FORM_CONTROL_TAGS
                if visible and strict_enabled and bool(el.get("receivesEvents", True)):
                    state = "usable"
                else:
                    state = "blocked"
                    if not visible:
                        reason = "hidden"
                    elif not strict_enabled:
                        reason = "disabled"
                    else:
                        reason = "covered"
    el["state"] = state
    el["state_reason"] = reason
    el["actionable"] = state == "usable"
