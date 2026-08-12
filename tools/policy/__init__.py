from __future__ import annotations

"""Pure URL/content-type policy shared by tools and services (no IO, no side effects).

Consumed by the crawl, download, and browser clusters via `tools.policy.*`.
"""

from tools.policy.crawl_policy import (
    BINARY_CONTENT_TYPES,
    build_exclude_domains,
    is_allowed_domain,
    is_binary_content_type,
)
from tools.policy.download_policy import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    DownloadPolicyError,
    is_allowed_type,
    validate_domain,
)
from tools.policy.link_policy import (
    DOCUMENT_EXTENSIONS,
    domain_of,
    filter_links,
    is_document_url,
    is_internal_link,
    is_same_site,
    normalize_domain,
    registrable_domain,
)

__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_EXTENSIONS",
    "BINARY_CONTENT_TYPES",
    "DOCUMENT_EXTENSIONS",
    "DownloadPolicyError",
    "build_exclude_domains",
    "domain_of",
    "filter_links",
    "is_allowed_domain",
    "is_allowed_type",
    "is_binary_content_type",
    "is_document_url",
    "is_internal_link",
    "is_same_site",
    "normalize_domain",
    "registrable_domain",
    "validate_domain",
]
