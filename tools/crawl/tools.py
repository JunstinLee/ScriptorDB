from __future__ import annotations

import json

from schemas.crawl_models import CrawlResult
from tools.policy.crawl_policy import is_allowed_domain
from tools.tool_decorators import db_tool

_ALL_LINKS_SUMMARY_LIMIT = 20


def _parse_domains(raw: str) -> list[str] | None:
    domains = [d.strip() for d in raw.split(",") if d.strip()]
    return domains or None


def _parse_schema(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _doc_type(url: str) -> str:
    path = url.split("?", 1)[0].split("#", 1)[0]
    dot = path.rfind(".")
    return path[dot + 1:].lower() if dot != -1 else ""


def _format_result(result: CrawlResult, domains: list[str] | None) -> str:
    if not result.success:
        return f"抓取失败: {result.error}"

    sections = [f"# {result.title or result.url}\n\n{result.markdown}"]

    info = []
    if result.document_links:
        docs = [
            {"url": link.url, "text": link.text, "类型": _doc_type(link.url)}
            for link in result.document_links
        ]
        info.append("文档链接：\n" + json.dumps(docs, ensure_ascii=False, indent=2))

    if result.links:
        links = result.links
        if domains:
            links = [link for link in links if is_allowed_domain(link.url, domains)]
        summary = [
            {"url": link.url, "text": link.text, "internal": link.is_internal}
            for link in links[:_ALL_LINKS_SUMMARY_LIMIT]
        ]
        info.append("全部链接（前 20 条）：\n" + json.dumps(summary, ensure_ascii=False, indent=2))

    if result.extracted_data:
        info.append("结构化数据：\n" + result.extracted_data)

    if info:
        sections.append("\n--- 结构化信息 ---\n" + "\n\n".join(info))

    return "\n".join(sections)


@db_tool(name="crawl_webpage", category="crawl", timeout=120)
async def crawl_webpage(
    ctx,
    url: str,
    allowed_domains: str = "",
    extraction_schema: str = "",
    wait_for_selector: str = "",
    pagination_next_selector: str = "",
    max_pages: int = 1,
    document_domains: str = "",
) -> str:
    from tools.crawl.service import crawl_url

    domains = _parse_domains(allowed_domains)
    doc_domains = _parse_domains(document_domains)
    schema = _parse_schema(extraction_schema)
    result: CrawlResult = await crawl_url(
        url,
        allowed_domains=domains,
        extraction_schema=schema,
        wait_for_selector=wait_for_selector.strip() or None,
        pagination_next_selector=pagination_next_selector.strip() or None,
        max_pages=max(max_pages, 1),
        document_domains=doc_domains,
    )
    return _format_result(result, domains)
