from __future__ import annotations

"""Crawl tool cluster: tool entry, orchestration, link extraction, rate limiting.

- `crawl_webpage` — agent tool entry (`tools.py`)
- `crawl_url` — fetch/markdown orchestration (`service.py`; import it directly)
- `extract_links` / `extract_with_schema` — pure helpers (`links.py`, `structured.py`)
- `RateLimiter` — per-domain politeness (`rate_limit.py`)

`service.py` is deliberately not re-exported here: it pulls in the Playwright
fetcher, which optional-dependency discovery must be able to skip.
"""

from tools.crawl.links import extract_links, filter_document_links, is_document_url
from tools.crawl.rate_limit import RateLimiter
from tools.crawl.structured import extract_rows, extract_with_schema
from tools.crawl.tools import crawl_webpage

__all__ = [
    "RateLimiter",
    "crawl_webpage",
    "extract_links",
    "extract_rows",
    "extract_with_schema",
    "filter_document_links",
    "is_document_url",
]
