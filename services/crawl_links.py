from __future__ import annotations

from urllib.parse import urlparse

from schemas.crawl_links import CrawlLink

DOCUMENT_EXTENSIONS = (".pdf", ".xls", ".xlsx", ".zip", ".csv")


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
) -> list[CrawlLink]:
    docs = [link for link in links if _is_document_url(link.url)]
    if not allowed_domains:
        return docs
    allowed = {_normalize(d) for d in allowed_domains if d}
    return [link for link in docs if _domain_of(link.url) in allowed]


def _is_document_url(url: str) -> bool:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(DOCUMENT_EXTENSIONS)


def _normalize(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def _domain_of(url: str) -> str:
    return _normalize(urlparse(url).hostname or "")


__all__ = ["extract_links", "filter_document_links", "DOCUMENT_EXTENSIONS"]
