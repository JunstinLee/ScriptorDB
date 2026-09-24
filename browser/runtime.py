from __future__ import annotations

import json

from playwright.async_api import Page


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


async def locate_elements(
    page: Page, text: str = "", role: str = "", scope: str = "visible"
) -> list[dict]:
    """Collect visible, interactive elements into ready-to-reuse selectors.

    Two-layer visibility: the JS pass does a first-layer layout screening (drops
    ``display:none`` / ``visibility:hidden`` / zero-size nodes and attaches graded
    ``enabled``/``inViewport``/``rect``/``visibility``/``inActive`` signals), then
    :func:`_confirm_actionable` does a second-layer Playwright actionability
    confirmation over the surviving candidates. Each entry carries
    ``{tag, text, role, id, value, selector, enabled, inViewport, inActive, rect,
    visibility, actionable}`` where ``selector`` can be passed straight back to
    ``browser_click``/``browser_fill``. ``text`` (substring of element text) and
    ``role`` optionally narrow the result. Raises nothing; returns ``[]`` on error.

    ``scope`` bounds how wide the scan goes: ``"visible"`` (default) keeps only
    components inside the viewport **and** the current active container so hidden
    sibling panels (ex. the coexisting visible/hidden month-panels of a date picker)
    stay out of the result; ``"container"`` keeps the whole active container even
    when slightly off-viewport; ``"page"`` drops the screening and returns the raw
    DOM matches. Breadth is capped here in the tool layer — callers can widen the
    scope but cannot bypass visibility/active-container filtering.
    """
    scope = (scope or "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"
    try:
        raw = await page.evaluate(
            """
            (filters) => {
                const tagSel = [
                    "a", "button", "input", "select", "textarea",
                    "li", "div", "span", "td", "label",
                    "[role='button']", "[role='link']", "[role='tab']",
                    "[role='menuitem']", "[role='checkbox']", "[role='radio']",
                    "[role='textbox']", "[role='combobox']", "[role='searchbox']",
                    "[role='switch']", "[role='option']"
                ].join(",");
                const scope = filters.scope || "visible";
                const vw = document.documentElement.clientWidth;
                const vh = document.documentElement.clientHeight;
                const laidOutCache = new WeakMap();
                const laidOut = (el) => {
                    let v = laidOutCache.get(el);
                    if (v !== undefined) return v;
                    const cs = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    v = !(cs.display === "none" || cs.visibility === "hidden" ||
                          r.width <= 0 || r.height <= 0);
                    laidOutCache.set(el, v);
                    return v;
                };
                const structCache = new WeakMap();
                const structCount = (el) => {
                    let v = structCache.get(el);
                    if (v === undefined) {
                        v = el.querySelectorAll(tagSel).length;
                        structCache.set(el, v);
                    }
                    return v;
                };
                const visCache = new WeakMap();
                const visibleCount = (el) => {
                    let v = visCache.get(el);
                    if (v !== undefined) return v;
                    let c = 0;
                    for (const d of el.querySelectorAll(tagSel)) {
                        if (laidOut(d)) c++;
                    }
                    visCache.set(el, c);
                    return c;
                };
                const activeCache = new WeakMap();
                const isActiveContainer = (el) => {
                    let v = activeCache.get(el);
                    if (v !== undefined) return v;
                    v = true;
                    const parent = el.parentElement;
                    if (parent && parent !== document.body && parent !== document.documentElement) {
                        let regions = 0, hasVisible = false, hasHidden = false;
                        for (const sib of parent.children) {
                            if (structCount(sib) >= 2) {
                                regions++;
                                if (visibleCount(sib) > 0) hasVisible = true;
                                else hasHidden = true;
                            }
                        }
                        if (regions >= 2 && hasVisible && hasHidden) {
                            v = visibleCount(el) > 0;
                        }
                    }
                    activeCache.set(el, v);
                    return v;
                };
                const containerOf = (node) => {
                    let p = node.parentElement;
                    while (p && p !== document.body && p !== document.documentElement) {
                        if (structCount(p) >= 2) {
                            const parent = p.parentElement;
                            if (parent && parent !== document.body && parent !== document.documentElement) {
                                let regions = 0, hasVisible = false, hasHidden = false;
                                for (const sib of parent.children) {
                                    if (structCount(sib) >= 2) {
                                        regions++;
                                        if (visibleCount(sib) > 0) hasVisible = true;
                                        else hasHidden = true;
                                    }
                                }
                                if (regions >= 2 && hasVisible && hasHidden) return p;
                            }
                        }
                        p = p.parentElement;
                    }
                    return null;
                };
                const nodes = Array.from(document.querySelectorAll(tagSel));
                const out = [];
                for (const n of nodes) {
                    const tag = n.tagName.toLowerCase();
                    if (tag === "input") {
                        const t = (n.type || "text").toLowerCase();
                        if (t === "hidden" || t === "submit" || t === "button" || t === "image") continue;
                    }
                    const style = getComputedStyle(n);
                    const rect = n.getBoundingClientRect();
                    const screened = style.display === "none" ||
                                     style.visibility === "hidden" ||
                                     rect.width <= 0 || rect.height <= 0;
                    if (screened && scope !== "page") continue;
                    let textVal = (n.innerText || n.getAttribute("aria-label") || "")
                        .replace(/\\s+/g, " ").trim().slice(0, 120);
                    if (filters.text) {
                        if (!textVal || !textVal.toLowerCase().includes(filters.text.toLowerCase())) continue;
                    }
                    let roleAttr = n.getAttribute("role") || "";
                    if (!roleAttr) {
                        if (tag === "a") roleAttr = "link";
                        else if (tag === "button") roleAttr = "button";
                        else if (tag === "select") roleAttr = "combobox";
                        else if (tag === "textarea") roleAttr = "textbox";
                        else if (tag === "input") {
                            const t = (n.type || "text").toLowerCase();
                            roleAttr = (t === "checkbox" || t === "radio") ? t : "textbox";
                        }
                    }
                    if (filters.role && roleAttr && !roleAttr.toLowerCase().includes(filters.role.toLowerCase())) continue;

                    let selector = "";
                    if (textVal) selector = "text=" + JSON.stringify(textVal.slice(0, 60));
                    else if (n.id) selector = "#" + CSS.escape(n.id);
                    else if (n.name) selector = tag + "[name=" + JSON.stringify(n.name) + "]";
                    else if (n.getAttribute("placeholder")) selector = tag + "[placeholder=" + JSON.stringify(n.getAttribute("placeholder")) + "]";
                    else if (n.getAttribute("aria-label")) selector = tag + "[aria-label=" + JSON.stringify(n.getAttribute("aria-label")) + "]";
                    else if (roleAttr) selector = "role=" + roleAttr;
                    else selector = tag;

                    const inViewport = rect.left < vw && rect.right > 0 &&
                                       rect.top < vh && rect.bottom > 0;
                    const pe = (style.pointerEvents || "auto").toLowerCase();
                    const disabled = n.disabled === true ||
                                     n.getAttribute("aria-disabled") === "true" ||
                                     pe === "none";

                    const container = containerOf(n);
                    const inActive = container ? isActiveContainer(container) : true;
                    if (scope === "visible" && !(inViewport && inActive)) continue;
                    if (scope === "container" && !inActive) continue;

                    out.push({
                        tag: tag,
                        text: textVal,
                        role: roleAttr,
                        id: n.id || "",
                        value: tag === "input" ? (n.value || "") : "",
                        selector: selector,
                        enabled: !disabled,
                        inViewport: inViewport,
                        inActive: inActive,
                        rect: {
                            x: Math.round(rect.left), y: Math.round(rect.top),
                            w: Math.round(rect.width), h: Math.round(rect.height)
                        },
                        visibility: {
                            display: style.display, visibility: style.visibility,
                            pointerEvents: pe
                        },
                    });
                }
                return out;
            }
            """,
            {"text": text or "", "role": role or "", "scope": scope},
        )
        if not isinstance(raw, list):
            return []
        elements = [d for d in raw if isinstance(d, dict)]
        await _confirm_actionable(page, elements)
        return elements
    except Exception:
        return []


async def _confirm_actionable(page: Page, elements: list[dict]) -> None:
    """Second-layer Playwright actionability confirmation over surviving candidates.

    Runs ``is_visible``/``is_enabled`` per element so "can this be operated now" is
    confirmed by real interaction checks rather than layout heuristics alone. Only
    already-screened candidates reach here, keeping the per-element round trips small.
    Sets ``actionable`` on each entry and mirrors it onto ``enabled`` when a handle
    could be resolved.
    """
    for el in elements:
        selector = el.get("selector") or ""
        confirmed: bool | None = None
        if selector:
            try:
                handle = await page.query_selector(selector)
                if handle is not None:
                    confirmed = bool(await handle.is_visible()) and bool(await handle.is_enabled())
            except Exception:
                confirmed = None
        if confirmed is None:
            el["actionable"] = bool(el.get("enabled", True))
        else:
            el["actionable"] = confirmed
            el["enabled"] = confirmed
