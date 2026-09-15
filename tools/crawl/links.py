from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from schemas.crawl_links import CrawlLink
from tools.policy.link_policy import (
    DOCUMENT_EXTENSIONS,
    domain_of,
    filter_links,
    is_document_url,
    is_internal_link,
)

_SKIP_HREF_PREFIXES = ("javascript:", "mailto:", "tel:", "data:", "about:", "#")


def _base_href(soup: BeautifulSoup, base_url: str) -> str:
    tag = soup.find("base", href=True)
    if tag is None:
        return base_url
    return urljoin(base_url, tag["href"]) or base_url


def extract_links(html: str, base_url: str = "") -> list[CrawlLink]:
    """Parse `<a href>` elements into CrawlLink entries, resolving relative URLs."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    resolved_base = _base_href(soup, base_url)

    out: list[CrawlLink] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.lower().startswith(_SKIP_HREF_PREFIXES):
            continue
        url = urljoin(resolved_base, href)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(CrawlLink(
            url=url,
            text=anchor.get_text(strip=True),
            title=anchor.get("title") or "",
            base_domain=domain_of(url),
            is_internal=is_internal_link(url, resolved_base) if resolved_base else False,
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
