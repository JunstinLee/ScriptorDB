from __future__ import annotations

from urllib.parse import urlparse

DOCUMENT_EXTENSIONS = (".pdf", ".xls", ".xlsx", ".zip", ".csv")

# Second-level public suffixes (e.g. "co.uk", "com.cn"): a registrable domain
# needs three labels under these. Everything else defaults to two labels.
_PUBLIC_SUFFIX_SECOND_LEVEL = {
    "ac.cn", "co.at", "co.in", "co.jp", "co.kr", "co.nz", "co.th", "co.uk",
    "com.au", "com.br", "com.cn", "com.co", "com.hk", "com.mx", "com.my",
    "com.ph", "com.sa", "com.sg", "com.tw", "com.tr", "com.vn", "edu.au",
    "edu.cn", "gov.cn", "gov.uk", "net.au", "net.cn", "net.in", "net.nz",
    "net.uk", "org.au", "org.cn", "org.in", "org.nz", "org.uk",
}


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def domain_of(url: str) -> str:
    return normalize_domain(urlparse(url).hostname or "")


def registrable_domain(host: str) -> str:
    """Return the registrable (eTLD+1) domain of a host, e.g. ``a.b.example.com`` -> ``example.com``."""
    h = normalize_domain(host)
    if not h:
        return ""
    labels = h.split(".")
    if len(labels) <= 2:
        return h
    tail = ".".join(labels[-2:])
    if tail in _PUBLIC_SUFFIX_SECOND_LEVEL and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail


def is_same_site(host_a: str, host_b: str) -> bool:
    """True when two hosts share a registrable domain (subdomains count as same-site)."""
    ra = registrable_domain(host_a)
    rb = registrable_domain(host_b)
    return bool(ra) and ra == rb


def is_internal_link(url: str, base_url: str) -> bool:
    host = urlparse(url).hostname or ""
    base_host = urlparse(base_url).hostname or ""
    return is_same_site(host, base_host)


def is_document_url(url: str) -> bool:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(DOCUMENT_EXTENSIONS)


def _page_in_scope(page_url: str, allowed_nav: set[str]) -> bool:
    if not allowed_nav:
        return True
    if not page_url:
        return True
    return domain_of(page_url) in allowed_nav


def filter_links(
    links: list,
    *,
    page_url: str = "",
    allowed_domains: list[str] | None = None,
    document_domains: list[str] | None = None,
    document_only: bool = False,
    keep_external_docs: bool = True,
) -> list:
    """Apply document-only and domain policy.

    Semantics: `allowed_domains` restricts *navigation* links only. Document
    links are treated as page content and are always kept while the source
    page is in scope (extraction already happened on that page), regardless of
    the document's host (e.g. a file CDN). `document_domains` remains an
    explicit additional allowlist for document links. Set `keep_external_docs`
    to False to restore the old "documents restricted to allowed domains" rule.
    """
    if document_only:
        links = [link for link in links if is_document_url(link.url)]
    allowed_nav = {normalize_domain(d) for d in allowed_domains or [] if d}
    allowed_doc = allowed_nav | {normalize_domain(d) for d in document_domains or [] if d}
    page_in_scope = _page_in_scope(page_url, allowed_nav)

    def keep(link) -> bool:
        domain = domain_of(link.url)
        if is_document_url(link.url):
            if keep_external_docs and page_in_scope:
                return True
            return not allowed_doc or domain in allowed_doc
        if document_only:
            return False
        return not allowed_nav or domain in allowed_nav

    return [link for link in links if keep(link)]


__all__ = [
    "DOCUMENT_EXTENSIONS",
    "normalize_domain",
    "domain_of",
    "registrable_domain",
    "is_same_site",
    "is_internal_link",
    "is_document_url",
    "filter_links",
]
