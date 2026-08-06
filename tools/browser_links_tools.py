from __future__ import annotations

import json
from urllib.parse import urlparse

from browser.links import LinkExtraction, extract_links, merge_extractions
from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from services.crawl_links import DOCUMENT_EXTENSIONS
from tools.browser import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser_links")

_NEXT_SELECTOR_CANDIDATES = (
    '[rel="next"]',
    ".pager-next",
    ".next",
    ".pagination-next",
    'button.next',
    '[aria-label*="next" i]',
)

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


async def _click_next(page, selector: str) -> bool:
    """Click the site-pagination "next" button; return False if unavailable."""
    sel = selector
    if not sel:
        for candidate in _NEXT_SELECTOR_CANDIDATES:
            if await page.query_selector(candidate) is not None:
                sel = candidate
                break
        if not sel:
            return False
    element = await page.query_selector(sel)
    if element is None:
        return False
    try:
        if await element.get_attribute("disabled") is not None:
            return False
        aria = await element.get_attribute("aria-disabled")
        if aria and str(aria).lower() == "true":
            return False
        await element.click()
        return True
    except Exception:
        try:
            clicked = await page.evaluate(
                "(s) => { const b = document.querySelector(s); if (b) { b.click(); return true; } return false; }",
                sel,
            )
            return bool(clicked)
        except Exception:
            return False


async def _settle_after_click(page) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    await page.wait_for_timeout(500)


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
    """提取页面链接并返回已去重、格式固定的最终列表。

    返回结果即为可直接呈现的最终数据（total/page/truncated/links），请直接
    根据结果回答用户；不要再用 run_python_code 等工具对链接列表做二次整理。

    高级参数（可选）：
    - wait_for_selector: 提取前等待该 CSS 选择器出现（动态渲染页面）；
    - pagination_next_selector: 网站分页器"下一页"选择器（留空则自动探测
      rel=next/.pager-next/.next 等常见选择器），配合 max_pages>1 点击翻页并
      合并全部页面的链接；
    - document_only: 仅保留文档链接（PDF/Excel/ZIP/CSV）；
    - allowed_domains: 允许的域名（逗号分隔），页面链接受此限制；
    - document_domains: 文档链接额外允许的域名（逗号分隔，如文件 CDN）。
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
        return f"该页没有链接（共 {total} 条，第 {page} 页超出范围）"

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

    summary = f"提取到 {total} 条链接（第 {page} 页）"
    if truncated:
        summary += "，已截断"
    body = {
        "total": total,
        "page": page,
        "truncated": truncated,
        "links": payload,
    }
    return f"{summary}:\n{json.dumps(body, ensure_ascii=False)}"


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


@db_tool(name="browser_get_tabs", category="browser", timeout=10, sequential=False)
async def browser_get_tabs(ctx: RunContext[Settings]) -> str:
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    tabs = manager.tabs.pages()
    if not tabs:
        return "No tabs open"
    active = manager.tabs.active_page()
    lines = []
    for i, tab in enumerate(tabs):
        parts = [f"[{i}]"]
        if tab is active:
            parts.append("ACTIVE")
        parts.append(tab.url)
        try:
            title = await tab.title()
        except Exception:
            title = ""
        if title:
            parts.append(title)
        lines.append(" ".join(parts))
    manager.record_action("get_tabs", f"{len(tabs)} tabs")
    return "\n".join(lines)


@db_tool(name="browser_switch_tab", category="browser", timeout=10, sequential=True)
async def browser_switch_tab(ctx: RunContext[Settings], index: int) -> str:
    manager, _ = _require_browser()
    if not manager.tabs.pages():
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    try:
        page = manager.tabs.switch_tab(index)
    except IndexError as e:
        return str(e)
    try:
        title = await page.title()
    except Exception:
        title = ""
    manager.record_action("switch_tab", f"index={index} url={page.url}")
    return f"Switched to tab {index}: {page.url} {title}".strip()
