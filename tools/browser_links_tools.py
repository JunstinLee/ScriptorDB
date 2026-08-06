from __future__ import annotations

import json

from browser.links import extract_links
from config.settings import Settings
from logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser_links")


@db_tool(name="browser_extract_links", category="browser", timeout=15, sequential=False)
async def browser_extract_links(
    ctx: RunContext[Settings],
    selector: str = "",
    max_links: int = 50,
    page: int = 1,
    include_external: bool = True,
    unique_only: bool = True,
    include_metadata: bool = False,
) -> str:
    """提取页面链接并返回已去重、格式固定的最终列表。

    返回结果即为可直接呈现的最终数据（total/page/truncated/links），请直接
    根据结果回答用户；不要再用 run_python_code 等工具对链接列表做二次整理。
    """
    manager, page_obj = _require_browser()
    if page_obj is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    try:
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

    manager.record_action("extract_links", f"{extraction.total} links")
    if extraction.total == 0:
        return "No links found on page"
    if not extraction.links:
        return f"该页没有链接（共 {extraction.total} 条，第 {page} 页超出范围）"

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
            for link in extraction.links
        ]
    else:
        payload = [
            {
                "text": link.text,
                "url": link.url,
                "new_tab": link.new_tab,
                "is_internal": link.is_internal,
            }
            for link in extraction.links
        ]

    summary = f"提取到 {extraction.total} 条链接（第 {page} 页）"
    if extraction.truncated:
        summary += "，已截断"
    body = {
        "total": extraction.total,
        "page": page,
        "truncated": extraction.truncated,
        "links": payload,
    }
    return f"{summary}:\n{json.dumps(body, ensure_ascii=False)}"


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
