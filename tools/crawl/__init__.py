from __future__ import annotations

"""Crawl tool cluster: tool entry (`crawl_webpage`).

Implementation lives in `tools.crawl.tools`; crawl orchestration stays in
`services.crawl_service` (imported lazily at call time). Importing this package
registers the `crawl_webpage` tool.
"""

from tools.crawl.tools import crawl_webpage  # noqa: F401

__all__ = ["crawl_webpage"]
