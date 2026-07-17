from __future__ import annotations

from dataclasses import dataclass


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
