from __future__ import annotations

import asyncio
import json
import traceback
from urllib.parse import urlparse

from core.logging_setup import get_logger
from schemas.crawl_links import CrawlLink
from schemas.crawl_models import CrawlResult
from tools.crawl.fetcher import RAW_PREFIX, fetch_pages
from tools.crawl.links import extract_links, filter_document_links, is_document_url
from tools.crawl.markdown import html_to_markdown
from tools.crawl.structured import extract_rows
from tools.policy.crawl_policy import is_binary_content_type

logger = get_logger("crawl")

MAX_MARKDOWN_LENGTH = 50000

DOCUMENT_MARKER = "This is a document (PDF/Excel/ZIP, etc.) — download it with download_file and parse it."

_CONTENT_TYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".csv": "text/csv",
}


def _normalize_url(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        raise ValueError("URL is empty")
    if stripped.startswith(RAW_PREFIX):
        return stripped
    parsed = urlparse(stripped)
    if not parsed.scheme:
        stripped = f"https://{stripped}"
        parsed = urlparse(stripped)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return stripped


def _guess_content_type(url: str) -> str | None:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    for ext, ct in _CONTENT_TYPE_BY_EXT.items():
        if path.endswith(ext):
            return ct
    return None


def _merge_links(acc: list[CrawlLink], new: list[CrawlLink]) -> None:
    seen = {link.url for link in acc}
    for link in new:
        if link.url and link.url not in seen:
            seen.add(link.url)
            acc.append(link)


def _merge_rows(acc: list[dict], new: list | None) -> None:
    if not new:
        return
    seen = {_row_key(row) for row in acc}
    for row in new:
        if not isinstance(row, dict):
            continue
        key = _row_key(row)
        if key not in seen:
            seen.add(key)
            acc.append(row)


def _row_key(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _serialize_rows(rows: list[dict]) -> str | None:
    if not rows:
        return None
    return json.dumps(rows, ensure_ascii=False)


async def _crawl_url_inner(
    url: str,
    allowed_domains: list[str] | None = None,
    extraction_schema: dict | None = None,
    wait_for_selector: str | None = None,
    pagination_next_selector: str | None = None,
    max_pages: int = 1,
    document_domains: list[str] | None = None,
    page_settle_ms: int = 800,
) -> CrawlResult:
    if not url.startswith(RAW_PREFIX) and is_document_url(url):
        logger.info("crawl url is a document by extension url=%s — routed to download tool", url)
        return CrawlResult(
            url=url,
            success=True,
            is_document=True,
            content_type=_guess_content_type(url),
            markdown=DOCUMENT_MARKER,
        )

    pages = await fetch_pages(
        url,
        wait_for_selector=wait_for_selector,
        pagination_next_selector=pagination_next_selector,
        max_pages=max(max_pages, 1),
        page_settle_ms=page_settle_ms,
    )
    if not pages:
        return CrawlResult(url=url, success=False, error="No response from crawler")

    if pages[0].error:
        return CrawlResult(url=url, success=False, error=pages[0].error)

    first = pages[0]
    content_type = first.content_type
    status_code = first.status_code
    title = first.title

    if is_binary_content_type(content_type):
        logger.info("crawl returned binary content_type=%s url=%s — routed to download tool", content_type, url)
        return CrawlResult(
            url=url,
            title=title,
            markdown=DOCUMENT_MARKER,
            status_code=status_code,
            success=True,
            content_type=content_type,
            is_document=True,
        )

    merged_links: list[CrawlLink] = []
    merged_rows: list[dict] = []
    for page in pages:
        _merge_links(merged_links, extract_links(page.html, page.final_url or url))
        if extraction_schema:
            _merge_rows(merged_rows, extract_rows(page.html, extraction_schema))

    raw_markdown = html_to_markdown(first.html, first.final_url or url)
    truncated = False
    if len(raw_markdown) > MAX_MARKDOWN_LENGTH:
        raw_markdown = raw_markdown[:MAX_MARKDOWN_LENGTH] + "\n\n[Content truncated — exceeded 50K characters]"
        truncated = True

    success = status_code is not None and 200 <= status_code < 400

    if not success and raw_markdown.strip():
        logger.warning(
            "crawl returned markdown but status_code=%s — treating as success",
            status_code,
        )
        success = True

    document_links = filter_document_links(merged_links, allowed_domains, document_domains, page_url=url)

    extracted_data = None
    if extraction_schema and success:
        extracted_data = _serialize_rows(merged_rows)

    return CrawlResult(
        url=url,
        title=title,
        markdown=raw_markdown,
        html=first.html,
        status_code=status_code,
        success=success,
        links=merged_links,
        document_links=document_links,
        content_type=content_type,
        truncated=truncated,
        extracted_data=extracted_data,
    )


async def crawl_url(
    url: str,
    timeout: int = 30,
    allowed_domains: list[str] | None = None,
    extraction_schema: dict | None = None,
    wait_for_selector: str | None = None,
    pagination_next_selector: str | None = None,
    max_pages: int = 1,
    document_domains: list[str] | None = None,
    page_settle_ms: int = 800,
) -> CrawlResult:
    try:
        normalized = _normalize_url(url)
    except ValueError as e:
        return CrawlResult(url=url, success=False, error=str(e))

    try:
        return await asyncio.wait_for(
            _crawl_url_inner(
                normalized,
                allowed_domains,
                extraction_schema,
                wait_for_selector,
                pagination_next_selector,
                max_pages,
                document_domains,
                page_settle_ms,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return CrawlResult(url=url, success=False, error="Request timed out")
    except Exception as e:
        logger.error("Unexpected crawl error for %s: %s\n%s", url, e, traceback.format_exc())
        return CrawlResult(url=url, success=False, error=str(e))


__all__ = ["crawl_url"]
