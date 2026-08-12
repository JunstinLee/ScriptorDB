from __future__ import annotations

from dataclasses import dataclass, field

from schemas.crawl_links import CrawlLink


@dataclass
class CrawlRequest:
    url: str
    timeout: int = 30
    output_format: str = "markdown"


@dataclass
class CrawlResult:
    url: str
    title: str | None = None
    markdown: str = ""
    html: str = ""
    status_code: int | None = None
    success: bool = False
    error: str | None = None
    links: list[CrawlLink] = field(default_factory=list)
    document_links: list[CrawlLink] = field(default_factory=list)
    content_type: str | None = None
    truncated: bool = False
    is_document: bool = False
    extracted_data: str | None = None
