from __future__ import annotations

import asyncio
import json
import traceback
from urllib.parse import urlparse
from uuid import uuid4

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

from logging_setup import get_logger
from schemas.crawl_links import CrawlLink
from schemas.crawl_models import CrawlResult
from services.crawl_links import extract_links, filter_document_links, is_document_url
from services.crawl_policy import build_exclude_domains, is_binary_content_type
from services.crawl_rate_limit import RateLimiter
from services.crawl_structured import extract_rows

logger = get_logger("crawl")

MAX_MARKDOWN_LENGTH = 50000

DOCUMENT_MARKER = "这是一个文档（PDF/Excel/ZIP 等），请使用 download_file 工具下载后解析。"

_CONTENT_TYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".csv": "text/csv",
}

_rate_limiter = RateLimiter()


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


def _extract_raw_markdown(result: object) -> str:
    md = getattr(result, "markdown", None)
    if isinstance(md, str):
        return md
    if md is not None:
        raw = getattr(md, "raw_markdown", None)
        if isinstance(raw, str):
            return raw
    return ""


def _extract_title(result: object) -> str | None:
    title = getattr(result, "title", None)
    meta = getattr(result, "metadata", None)
    if not title and meta:
        title = getattr(meta, "title", None)
        if title is None and hasattr(meta, "get"):
            title = meta.get("title")
    return title or None


def _extract_content_type(result: object) -> str | None:
    headers = getattr(result, "response_headers", None)
    if not headers or not isinstance(headers, dict):
        return None
    ct = None
    for key, value in headers.items():
        if str(key).lower() == "content-type":
            ct = value
            break
    if not ct:
        return None
    return str(ct).split(";", 1)[0].strip().lower()


def _extract_html(result: object) -> str:
    return getattr(result, "html", "") or ""


def _url_is_document(url: str) -> bool:
    return is_document_url(url)


def _guess_content_type(url: str) -> str | None:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    for ext, ct in _CONTENT_TYPE_BY_EXT.items():
        if path.endswith(ext):
            return ct
    return None


def _extract_fit_html(result: object) -> str:
    for attr in ("fit_html", "cleaned_html", "html"):
        value = getattr(result, attr, None)
        if isinstance(value, bytes):
            value = value.decode(errors="ignore")
        if isinstance(value, str) and value:
            return value
    return ""


def _pagination_click_js(selector: str) -> str:
    """JS that clicks the next-page button, ignoring disabled/absent elements."""
    return (
        "(() => {"
        f"const btn = document.querySelector({selector!r});"
        "if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') {"
        "btn.click();"
        "}"
        "})()"
    )


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
    if _url_is_document(url):
        logger.info("crawl url is a document by extension url=%s — routed to download tool", url)
        return CrawlResult(
            url=url,
            success=True,
            is_document=True,
            content_type=_guess_content_type(url),
            markdown=DOCUMENT_MARKER,
        )

    config_kwargs: dict = {
        "cache_mode": CacheMode.ENABLED,
        "exclude_domains": build_exclude_domains(allowed_domains),
    }
    if wait_for_selector:
        config_kwargs["wait_for"] = f"css:{wait_for_selector}"
    else:
        config_kwargs["wait_until"] = "networkidle"
    config = CrawlerRunConfig(**config_kwargs)

    domain = urlparse(url).hostname or ""
    needs_pagination = bool(pagination_next_selector) and max_pages > 1
    session_id = f"crawl-{uuid4().hex}" if needs_pagination else None

    collected: list[object] = []
    merged_links: list[CrawlLink] = []
    merged_rows: list[dict] = []

    async with AsyncWebCrawler() as crawler:
        await _rate_limiter.acquire(domain)
        try:
            if needs_pagination:
                first = await crawler.arun(url=url, config=config, session_id=session_id)
            else:
                first = await crawler.arun(url=url, config=config)
            if first:
                collected.append(first)
                _merge_links(merged_links, extract_links(first))
                if extraction_schema:
                    _merge_rows(merged_rows, extract_rows(_extract_fit_html(first), extraction_schema))

            for _ in range(max_pages - 1):
                page_config = CrawlerRunConfig(
                    js_only=True,
                    js_code=[_pagination_click_js(pagination_next_selector or "")],
                    wait_until="domcontentloaded",
                    delay_before_return_html=page_settle_ms / 1000.0,
                    cache_mode=CacheMode.BYPASS,
                )
                page_result = await crawler.arun(url=url, config=page_config, session_id=session_id)
                if not page_result:
                    break
                collected.append(page_result)
                before = len(merged_links)
                _merge_links(merged_links, extract_links(page_result))
                if extraction_schema:
                    _merge_rows(merged_rows, extract_rows(_extract_fit_html(page_result), extraction_schema))
                if len(merged_links) == before:
                    break
        finally:
            _rate_limiter.release(domain)

    if not collected or collected[0] is None:
        return CrawlResult(url=url, success=False, error="No response from crawler")

    result = collected[0]
    content_type = _extract_content_type(result)
    status_code = _extract_status_code(result)
    title = _extract_title(result)

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

    raw_markdown = _extract_raw_markdown(result)
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
        html=_extract_html(result),
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
