from __future__ import annotations

import json
from urllib.parse import urlparse

from browser.links import LinkExtraction, extract_links, merge_extractions
from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from services.crawl_links import DOCUMENT_EXTENSIONS
from tools.browser_common import _check_blocked, _click_next, _require_browser, _settle_after_click
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.links")

_SITE_PAGE_SNAPSHOT_LIMIT = 500


def _is_document_url(url: str) -> bool:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(DOCUMENT_EXTENSIONS)


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def _domain_of(url: str) -> str:
    return _normalize_domain(urlparse(url).hostname or "")


def _filter_links(
    links: list,
    document_only: bool,
    domains: list[str] | None,
    document_domains: list[str] | None,
) -> list:
    """Apply document-only and domain policy.

    Navigation links are restricted to `domains`; document links (PDF/Excel/
    ZIP/CSV) are additionally allowed on `document_domains` (e.g. a file CDN).
    """
    if document_only:
        links = [link for link in links if _is_document_url(link.url)]
    if not domains and not document_domains:
        return links
    allowed_nav = {_normalize_domain(d) for d in domains or []}
    allowed_doc = allowed_nav | {_normalize_domain(d) for d in document_domains or []}

    def keep(link) -> bool:
        domain = _domain_of(link.url)
        if _is_document_url(link.url):
            return not allowed_doc or domain in allowed_doc
        return not allowed_nav or domain in allowed_nav

    return [link for link in links if keep(link)]


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


@db_tool(name="browser_extract_links", category="browser", timeout=15, sequential=False)
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
) -> str:
    """Extract page links and return a deduplicated, final formatted list.

    The result is the final, directly presentable data (total/page/truncated/links).
    Answer the user based on it directly; do not re-process it with run_python_code.

    Optional advanced parameters:
    - wait_for_selector: wait for this CSS selector before extracting (dynamically rendered pages);
    - pagination_next_selector: the "next page" selector of the site pager (auto-detects
      rel=next/.pager-next/.next when left empty); with max_pages>1 it clicks through pages
      and merges links from all pages;
    - document_only: keep only document links (PDF/Excel/ZIP/CSV);
    - allowed_domains: allowed domains (comma separated), page links are restricted to these;
    - document_domains: additional domains allowed for document links (comma separated, e.g. a file CDN).
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    domains = [d.strip() for d in allowed_domains.split(",") if d.strip()] or None
    doc_domains = [d.strip() for d in document_domains.split(",") if d.strip()] or None

    try:
        if wait_for_selector:
            await page_obj.wait_for_selector(wait_for_selector, timeout=10000)

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
            )
    except Exception as e:
        manager.record_action("extract_links", f"error: {e}", success=False)
        return f"Link extraction failed: {e}"

    raw_total = extraction.total
    links = _filter_links(extraction.links, document_only, domains, doc_domains)
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
        return "No links found on page"
    if not links:
        return f"No links on this page (total {total}, page {page} is out of range)"

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

    summary = f"Extracted {total} links (page {page})"
    if truncated:
        summary += ", truncated"
    body = {
        "total": total,
        "page": page,
        "truncated": truncated,
        "links": payload,
    }
    return f"{summary}:\n{json.dumps(body, ensure_ascii=False)}"
