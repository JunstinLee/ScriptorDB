from __future__ import annotations

from schemas.crawl_links import CrawlLink
from tools.policy.link_policy import (
    DOCUMENT_EXTENSIONS,
    domain_of,
    filter_links,
    is_document_url,
)


def extract_links(result: object) -> list[CrawlLink]:
    """Map crawl4ai `result.links` (internal/external) into CrawlLink list."""
    links = getattr(result, "links", None)
    if not links or not isinstance(links, dict):
        return []
    out: list[CrawlLink] = []
    for is_internal, key in ((True, "internal"), (False, "external")):
        for item in links.get(key) or []:
            if not isinstance(item, dict):
                continue
            href = item.get("href") or ""
            if not href:
                continue
            out.append(CrawlLink(
                url=href,
                text=item.get("text") or "",
                title=item.get("title") or "",
                base_domain=item.get("base_domain") or "",
                is_internal=is_internal,
            ))
    return out


def filter_document_links(
    links: list[CrawlLink],
    allowed_domains: list[str] | None = None,
    document_domains: list[str] | None = None,
    page_url: str = "",
) -> list[CrawlLink]:
    """Filter document links.

    Document links are treated as page content: while the source page is in
    scope (`allowed_domains` empty, or the page URL is on an allowed domain),
    external document links (e.g. on a file CDN) are kept. `document_domains`
    remains an explicit additional allowlist for document links.
    """
    return filter_links(
        links,
        page_url=page_url,
        allowed_domains=allowed_domains,
        document_domains=document_domains,
        document_only=True,
    )


__all__ = [
    "extract_links",
    "filter_document_links",
    "DOCUMENT_EXTENSIONS",
    "is_document_url",
    "domain_of",
]
