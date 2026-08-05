from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import Page

from logging_setup import get_logger

logger = get_logger("browser.links")


@dataclass
class StructuredLink:
    text: str = ""
    url: str = ""
    title: str = ""
    base_domain: str = ""
    target: str = ""
    new_tab: bool = False
    is_internal: bool = True


_LINK_EXTRACT_JS = """
([selector, maxLinks]) => {
    const anchors = selector
        ? document.querySelectorAll(selector)
        : document.querySelectorAll('a[href]');
    const baseUrl = new URL(document.baseURI);
    const links = [];
    for (const a of anchors) {
        const rawHref = a.getAttribute('href');
        if (!rawHref || !rawHref.trim()) continue;
        let abs;
        try {
            abs = new URL(rawHref, baseUrl.href).href;
        } catch (e) {
            continue;
        }
        let parsed;
        try {
            parsed = new URL(abs);
        } catch (e) {
            continue;
        }
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') continue;
        links.push({
            text: (a.innerText || '').trim(),
            url: abs,
            title: a.getAttribute('title') || '',
            base_domain: parsed.hostname,
            target: a.getAttribute('target') || '',
            new_tab: a.target === '_blank',
            is_internal: parsed.hostname === baseUrl.hostname,
        });
        if (links.length >= maxLinks) break;
    }
    return links;
}
"""


async def extract_links(
    page: Page,
    selector: str | None = None,
    max_links: int = 100,
) -> list[StructuredLink]:
    raw = await page.evaluate(_LINK_EXTRACT_JS, [selector or "", max_links])
    if not raw:
        return []
    return [StructuredLink(**item) for item in raw]


__all__ = ["StructuredLink", "extract_links"]
