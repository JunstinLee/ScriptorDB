from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

from schemas.crawl_models import CrawlResult

MAX_MARKDOWN_LENGTH = 50000


def _normalize_url(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        raise ValueError("URL is empty")
    parsed = urlparse(stripped)
    if not parsed.scheme:
        stripped = f"https://{stripped}"
        parsed = urlparse(stripped)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return stripped


async def _crawl_url_inner(url: str) -> CrawlResult:
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)

    if not result:
        return CrawlResult(url=url, success=False, error="No response from crawler")

    markdown = result.markdown or result.markdown_v2 or ""
    if len(markdown) > MAX_MARKDOWN_LENGTH:
        markdown = markdown[:MAX_MARKDOWN_LENGTH] + "\n\n[Content truncated — exceeded 50K characters]"

    title = result.title
    if not title and result.metadata:
        title = getattr(result.metadata, "title", None) or result.metadata.get("title") if hasattr(result.metadata, "get") else None

    status_code = getattr(result, "status_code", None)
    success = status_code is not None and 200 <= status_code < 400

    return CrawlResult(
        url=url,
        title=title,
        markdown=markdown,
        html=getattr(result, "html", "") or "",
        status_code=status_code,
        success=success,
    )


async def crawl_url(url: str, timeout: int = 30) -> CrawlResult:
    try:
        normalized = _normalize_url(url)
    except ValueError as e:
        return CrawlResult(url=url, success=False, error=str(e))

    try:
        return await asyncio.wait_for(_crawl_url_inner(normalized), timeout=timeout)
    except asyncio.TimeoutError:
        return CrawlResult(url=url, success=False, error="Request timed out")
    except Exception as e:
        return CrawlResult(url=url, success=False, error=str(e))


__all__ = ["crawl_url"]
