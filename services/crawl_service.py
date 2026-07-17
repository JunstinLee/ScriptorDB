from __future__ import annotations

import asyncio
import traceback
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

from logging_setup import get_logger
from schemas.crawl_models import CrawlResult

logger = get_logger("crawl")

MAX_MARKDOWN_LENGTH = 50000


def _extract_status_code(result: object) -> int | None:
    for attr in ("status_code", "response_status", "http_status_code"):
        val = getattr(result, attr, None)
        if isinstance(val, int):
            return val

    resp = getattr(result, "response", None)
    if resp is not None:
        for attr in ("status_code", "status"):
            val = getattr(resp, attr, None)
            if isinstance(val, int):
                return val

    return None


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

    raw_markdown = result.markdown or result.markdown_v2 or ""
    if len(raw_markdown) > MAX_MARKDOWN_LENGTH:
        raw_markdown = raw_markdown[:MAX_MARKDOWN_LENGTH] + "\n\n[Content truncated — exceeded 50K characters]"

    title = getattr(result, "title", None)
    if not title and result.metadata:
        title = getattr(result.metadata, "title", None)
        if title is None and hasattr(result.metadata, "get"):
            title = result.metadata.get("title")

    status_code = _extract_status_code(result)
    success = status_code is not None and 200 <= status_code < 400

    if not success and raw_markdown.strip():
        logger.warning(
            "crawl returned markdown but status_code=%s — treating as success",
            status_code,
        )
        success = True

    return CrawlResult(
        url=url,
        title=title,
        markdown=raw_markdown,
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
        logger.error("Unexpected crawl error for %s: %s\n%s", url, e, traceback.format_exc())
        return CrawlResult(url=url, success=False, error=str(e))


__all__ = ["crawl_url"]
