from __future__ import annotations

import json

from playwright.async_api import Page


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
        return f"Query text all error: {e}"


async def query_attr(page: Page, selector: str, attr: str) -> str:
    try:
        element = await page.query_selector(selector)
        if element is None:
            return f"No element found for selector: {selector}"
        value = await element.get_attribute(attr)
        return value if value is not None else f"Attribute '{attr}' not found on {selector}"
    except Exception as e:
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
