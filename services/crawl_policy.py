from __future__ import annotations

from urllib.parse import urlparse

BINARY_CONTENT_TYPES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-gzip",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
    "application/x-msdownload",
    "application/x-rar-compressed",
}


def is_binary_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.split(";", 1)[0].strip().lower() in BINARY_CONTENT_TYPES


def build_exclude_domains(allowed_domains: list[str] | None) -> list[str]:
    """Map an allowlist to crawl4ai's `exclude_domains`.

    crawl4ai has no whitelist primitive, so a whitelist cannot be expressed as
    exclude_domains; enforcement is done post-hoc by `is_allowed_domain` /
    `services.crawl_links.filter_document_links`. Returns [] to keep crawl-time
    link collection unfiltered.
    """
    return []


def is_allowed_domain(url: str, allowed_domains: list[str] | None) -> bool:
    if not allowed_domains:
        return True
    allowed = {_normalize(d) for d in allowed_domains if d}
    return _domain_of(url) in allowed


def _normalize(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def _domain_of(url: str) -> str:
    return _normalize(urlparse(url).hostname or "")


__all__ = [
    "is_binary_content_type",
    "build_exclude_domains",
    "is_allowed_domain",
    "BINARY_CONTENT_TYPES",
]
