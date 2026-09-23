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


async def locate_elements(page: Page, text: str = "", role: str = "") -> list[dict]:
    """Collect interactive elements on the page into ready-to-reuse selectors.

    Each entry carries ``{tag, text, role, id, value, selector}`` where ``selector``
    is a Playwright engine selector that can be passed straight back to
    ``browser_click``/``browser_fill``. ``text`` (substring of element text) and
    ``role`` optionally narrow the result. Raises nothing; returns ``[]`` on error.
    """
    try:
        raw = await page.evaluate(
            """
            (filters) => {
                const tagSel = [
                    "a", "button", "input", "select", "textarea",
                    "[role='button']", "[role='link']", "[role='tab']",
                    "[role='menuitem']", "[role='checkbox']", "[role='radio']",
                    "[role='textbox']", "[role='combobox']", "[role='searchbox']",
                    "[role='switch']", "[role='option']"
                ].join(",");
                const nodes = Array.from(document.querySelectorAll(tagSel));
                const out = [];
                for (const n of nodes) {
                    const tag = n.tagName.toLowerCase();
                    if (tag === "input") {
                        const t = (n.type || "text").toLowerCase();
                        if (t === "hidden" || t === "submit" || t === "button" || t === "image") continue;
                    }
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

                    out.push({
                        tag: tag,
                        text: textVal,
                        role: roleAttr,
                        id: n.id || "",
                        value: tag === "input" ? (n.value || "") : "",
                        selector: selector,
                    });
                }
                return out;
            }
            """,
            {"text": text or "", "role": role or ""},
        )
        if not isinstance(raw, list):
            return []
        return [d for d in raw if isinstance(d, dict)]
    except Exception:
        return []
