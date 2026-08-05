from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_EXTENSIONS = {"pdf", "xls", "xlsx", "zip", "csv"}

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "application/x-zip-compressed",
    "text/csv",
}

# Binary-ish fallbacks for Excel/CVS served without a precise subtype.
_FALLBACK_CONTENT_TYPES = {"application/octet-stream", "application/binary"}


class DownloadPolicyError(Exception):
    pass


def validate_domain(url: str, allowed_domains: list[str] | None) -> None:
    if not allowed_domains:
        raise DownloadPolicyError("no allowed domains provided; a domain whitelist is required")
    allowed = {_normalize(d) for d in allowed_domains if d}
    if not allowed:
        raise DownloadPolicyError("no allowed domains provided; a domain whitelist is required")
    if _domain_of(url) not in allowed:
        raise DownloadPolicyError(f"domain {_domain_of(url) or url!r} is not in the allowed domains")


def is_allowed_type(content_type: str | None, ext: str | None) -> bool:
    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct in ALLOWED_CONTENT_TYPES:
            return True
        if ct in _FALLBACK_CONTENT_TYPES and ext in ALLOWED_EXTENSIONS:
            return True
    if ext and ext.lower().lstrip(".") in ALLOWED_EXTENSIONS:
        return True
    return False


def _normalize(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def _domain_of(url: str) -> str:
    return _normalize(urlparse(url).hostname or "")


__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_EXTENSIONS",
    "DownloadPolicyError",
    "is_allowed_type",
    "validate_domain",
]
