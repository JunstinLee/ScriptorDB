from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrawlLink:
    url: str = ""
    text: str = ""
    title: str = ""
    base_domain: str = ""
    is_internal: bool = True


__all__ = ["CrawlLink"]
