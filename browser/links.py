from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class LinkExtraction:
    total: int = 0
    truncated: bool = False
    links: list[StructuredLink] = field(default_factory=list)


_LINK_EXTRACT_JS = """
([selector, offset, limit, includeExternal, uniqueOnly]) => {
    const anchors = selector
        ? document.querySelectorAll(selector)
        : document.querySelectorAll('a[href]');
    const baseUrl = new URL(document.baseURI);
    const seen = new Set();
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
        const isInternal = parsed.hostname === baseUrl.hostname;
        if (!includeExternal && !isInternal) continue;
        if (uniqueOnly) {
            if (seen.has(abs)) continue;
            seen.add(abs);
        }
        links.push({
            text: (a.innerText || '').trim(),
            url: abs,
            title: a.getAttribute('title') || '',
            base_domain: parsed.hostname,
            target: a.getAttribute('target') || '',
            new_tab: a.target === '_blank',
            is_internal: isInternal,
        });
    }
    const total = links.length;
    return { total, links: links.slice(offset, offset + limit) };
}
"""


async def extract_links(
    page: Page,
    selector: str | None = None,
    limit: int = 50,
    include_external: bool = True,
    unique_only: bool = True,
    offset: int = 0,
) -> LinkExtraction:
    raw = await page.evaluate(
        _LINK_EXTRACT_JS,
        [selector or "", offset, limit, include_external, unique_only],
    )
    if not raw:
        return LinkExtraction(total=0, truncated=False, links=[])
    total = int(raw.get("total") or 0)
    links = [StructuredLink(**item) for item in raw.get("links") or []]
    truncated = offset + len(links) < total
    return LinkExtraction(total=total, truncated=truncated, links=links)


__all__ = ["LinkExtraction", "StructuredLink", "extract_links"]
