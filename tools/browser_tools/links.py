from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from browser.links import LinkExtraction, extract_links, merge_extractions
from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from services.link_policy import domain_of, filter_links, is_document_url, is_internal_link
from tools.browser_common import _check_blocked, _click_next, _require_browser, _settle_after_click
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.links")

_SITE_PAGE_SNAPSHOT_LIMIT = 500
_MAX_REDIRECT_RESOLUTIONS = 50
_MAX_REDIRECT_CONCURRENCY = 5
_REDIRECT_TIMEOUT_MS = 8000


async def _follow_redirect(page_obj, url: str) -> str | None:
    request = getattr(page_obj, "request", None)
    if request is None:
        return None
    for method in ("head", "get"):
        try:
            resp = await getattr(request, method)(
                url,
                max_redirects=10,
                timeout=_REDIRECT_TIMEOUT_MS,
            )
            final_url = getattr(resp, "url", None)
            if isinstance(final_url, str) and final_url:
                return final_url
        except Exception:
            continue
    return None


async def _resolve_redirects(
    page_obj,
    links: list,
    page_url: str,
) -> list:
    """Follow redirects for candidate links and update URL / internal flags.

    Only links that are not already same-site document URLs are resolved (keeps
    the common case fast); resolved links get their final URL, base_domain and
    is_internal recomputed. Resolution is capped and failure keeps the original.
    """
    out = list(links)
    candidates: list[tuple[int, object]] = []
    for index, link in enumerate(links):
        if is_document_url(link.url) and is_internal_link(link.url, page_url):
            continue
        if len(candidates) >= _MAX_REDIRECT_RESOLUTIONS:
            break
        candidates.append((index, link))

    semaphore = asyncio.Semaphore(_MAX_REDIRECT_CONCURRENCY)

    async def resolve_one(link):
        async with semaphore:
            final_url = await _follow_redirect(page_obj, link.url)
        if final_url and final_url != link.url:
            link.url = final_url
            link.base_domain = domain_of(final_url)
            link.is_internal = is_internal_link(final_url, page_url)
        return link

    resolved = await asyncio.gather(*(resolve_one(link) for _, link in candidates))
    for (index, _), link in zip(candidates, resolved):
        out[index] = link
    return out


def _dedupe_by_url(links: list) -> list:
    seen: set[str] = set()
    out: list = []
    for link in links:
        if link.url in seen:
            continue
        seen.add(link.url)
        out.append(link)
    return out


async def _extract_across_site_pages(
    page_obj,
    selector: str | None,
    include_external: bool,
    unique_only: bool,
    pagination_next_selector: str,
    max_pages: int,
) -> LinkExtraction:
    """Click through the site pager and merge link snapshots across pages."""
    extractions: list[LinkExtraction] = []
    seen: set[str] = set()
    for i in range(max_pages):
        extraction = await extract_links(
            page_obj,
            selector,
            limit=_SITE_PAGE_SNAPSHOT_LIMIT,
            include_external=include_external,
            unique_only=unique_only,
            offset=0,
            base_url=page_obj.url,
        )
        new_links = [link for link in extraction.links if link.url not in seen]
        seen.update(link.url for link in extraction.links)
        extractions.append(extraction)
        if i < max_pages - 1:
            if not await _click_next(page_obj, pagination_next_selector):
                break
            await _settle_after_click(page_obj)
        if not new_links and i > 0:
            break
    return merge_extractions(extractions)


@db_tool(name="browser_extract_links", category="browser", timeout=60, sequential=False)
async def browser_extract_links(
    ctx: RunContext[Settings],
    selector: str = "",
    max_links: int = 50,
    page: int = 1,
    include_external: bool = True,
    unique_only: bool = True,
    include_metadata: bool = False,
    wait_for_selector: str = "",
    pagination_next_selector: str = "",
    max_pages: int = 1,
    document_only: bool = False,
    allowed_domains: str = "",
    document_domains: str = "",
    resolve_redirects: bool = True,
) -> dict:
    """Extract page links and return a deduplicated, final structured list.

    The result is the final, directly presentable data (total/page/truncated/links).
    The returned links are already deduplicated and structured — no further parsing,
    transformation, or computation is needed; answer the user based on them directly.

    Optional advanced parameters:
    - wait_for_selector: wait for this CSS selector before extracting (dynamically rendered pages);
    - pagination_next_selector: the "next page" selector of the site pager (auto-detects
      rel=next/.pager-next/.next when left empty); with max_pages>1 it clicks through pages
      and merges links from all pages;
    - document_only: keep only document links (PDF/Excel/ZIP/CSV);
    - allowed_domains: allowed domains (comma separated), navigation links are restricted to these;
      document links are treated as page content and are kept regardless of their host;
    - document_domains: additional domains allowed for document links (comma separated, e.g. a file CDN);
    - resolve_redirects: follow redirects for candidate links and classify them by their
      final URL (on by default; capped to 50 resolutions per call).
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return {"error": "Browser not launched. Please call browser_launch first."}
    if blocked := _check_blocked(manager):
        return {"error": blocked}

    domains = [d.strip() for d in allowed_domains.split(",") if d.strip()] or None
    doc_domains = [d.strip() for d in document_domains.split(",") if d.strip()] or None
    if document_only:
        include_external = True

    try:
        if wait_for_selector:
            await page_obj.wait_for_selector(wait_for_selector, timeout=10000)

        page_url = page_obj.url if isinstance(page_obj.url, str) else ""

        if max_pages > 1:
            extraction = await _extract_across_site_pages(
                page_obj,
                selector or None,
                include_external,
                unique_only,
                pagination_next_selector,
                max_pages,
            )
        else:
            extraction = await extract_links(
                page_obj,
                selector or None,
                limit=max_links,
                include_external=include_external,
                unique_only=unique_only,
                offset=(max(page, 1) - 1) * max_links,
                base_url=page_url,
            )
        if resolve_redirects:
            extraction.links = await _resolve_redirects(page_obj, extraction.links, page_url)
            extraction.links = _dedupe_by_url(extraction.links)
    except Exception as e:
        manager.record_action("extract_links", f"error: {e}", success=False)
        return {"error": f"Link extraction failed: {e}"}

    raw_total = extraction.total
    links = filter_links(
        extraction.links,
        page_url=page_url,
        allowed_domains=domains,
        document_domains=doc_domains,
        document_only=document_only,
    )
    offset = (max(page, 1) - 1) * max_links
    if max_pages > 1:
        total = len(links)
        links = links[offset : offset + max_links]
        truncated = offset + len(links) < total
    else:
        total = raw_total
        truncated = offset + len(links) < raw_total

    manager.record_action("extract_links", f"{total} links")
    if total == 0:
        return {"total": 0, "page": max(page, 1), "truncated": False, "links": []}
    if not links:
        return {
            "total": total,
            "page": max(page, 1),
            "truncated": False,
            "links": [],
        }

    if include_metadata:
        payload = [
            {
                "text": link.text,
                "url": link.url,
                "new_tab": link.new_tab,
                "is_internal": link.is_internal,
                "title": link.title,
                "base_domain": link.base_domain,
                "target": link.target,
            }
            for link in links
        ]
    else:
        payload = [
            {
                "text": link.text,
                "url": link.url,
                "new_tab": link.new_tab,
                "is_internal": link.is_internal,
            }
            for link in links
        ]

    return {
        "total": total,
        "page": max(page, 1),
        "truncated": truncated,
        "links": payload,
    }
