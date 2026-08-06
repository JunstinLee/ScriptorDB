from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from logging_setup import get_logger

logger = get_logger("tool_middleware")

_BLOCKED_TOOLS = {
    "browser_query",
    "browser_evaluate",
    "browser_get_text",
    "browser_extract_links",
}

_DOC_KEYWORDS = (
    "文档",
    "抓取",
    "爬取",
    "提取",
    "链接",
    "pdf",
    "excel",
    "zip",
    "csv",
    "download",
    "document",
    "crawl",
    "extract",
    "filing",
)

_URL_PATH_SIGNALS = ("filings", "documents", "docs", "download", "archive")

_URL_RE = re.compile(r"https?://[^\s\"'<>，。；）)】\]}]+")

_SWITCH_LABEL = (
    "[Middleware] {tool_name} 调用被拦截（当前任务属于文档提取场景，低级别浏览器工具不适合）。\n"
    "已自动切换执行 {replacement}，参数：{args}\n"
    "返回结果即最终数据，请直接使用；不要再调用 browser_query / browser_evaluate / "
    "browser_get_text 等低级提取工具。\n\n{result}"
)


def _texts_from_context(ctx) -> list[str]:
    texts: list[str] = []
    prompt = getattr(ctx, "prompt", None)
    if isinstance(prompt, str):
        texts.append(prompt)
    for message in getattr(ctx, "messages", None) or []:
        for part in getattr(message, "parts", None) or []:
            content = getattr(part, "content", None)
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        texts.append(item)
                    elif hasattr(item, "content") and isinstance(getattr(item, "content", None), str):
                        texts.append(item.content)
    return texts


def _current_page_url() -> str | None:
    try:
        from browser import get_manager

        page = get_manager().page()
        if page is None:
            return None
        url = page.url
        return url if url and not url.startswith("about:") else None
    except Exception:
        return None


def _target_url_from_prompt(ctx) -> str | None:
    for text in _texts_from_context(ctx):
        match = _URL_RE.search(text)
        if match:
            return match.group(0)
    return None


def _is_document_discovery(ctx) -> bool:
    texts = _texts_from_context(ctx)
    blob = " ".join(texts).lower()
    hits = sum(1 for keyword in _DOC_KEYWORDS if keyword in blob)
    if hits >= 2:
        return True
    url = _current_page_url()
    if url:
        path = urlparse(url).path.lower()
        if any(signal in path for signal in _URL_PATH_SIGNALS):
            return True
    return False


def _same_domain(a: str, b: str) -> bool:
    def normalize(url: str) -> str:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.")

    return bool(normalize(a)) and normalize(a) == normalize(b)


def _find_tool_func(name: str):
    from tools.tool_decorators import get_all_tool_defs

    for tool_def in get_all_tool_defs():
        if tool_def.name == name:
            return tool_def.func
    return None


def _label(tool_name: str, replacement: str, kwargs: dict, result: str) -> str:
    return _SWITCH_LABEL.format(
        tool_name=tool_name,
        replacement=replacement,
        args=json.dumps(kwargs, ensure_ascii=False),
        result=result,
    )


async def evaluate_call(ctx, tool_name: str) -> str:
    """Decide whether a browser tool call may execute.

    Returns "allow" (execute normally) or "switch" (block and auto-switch to a
    more appropriate tool). Fails open: any uncertainty → "allow".
    """
    if tool_name not in _BLOCKED_TOOLS:
        return "allow"
    if ctx is None or getattr(ctx, "deps", None) is None:
        return "allow"
    if not _is_document_discovery(ctx):
        return "allow"
    if not (_target_url_from_prompt(ctx) or _current_page_url()):
        return "allow"
    logger.info("tool middleware: blocking %s — document discovery detected, switching tool", tool_name)
    return "switch"


async def execute_switch(ctx, tool_name: str, args: dict) -> str:
    """Execute the replacement tool and return its labeled result."""
    current = _current_page_url()
    target = _target_url_from_prompt(ctx)

    if current and (not target or _same_domain(current, target)):
        return await _run_browser_extract_links(ctx, args, current)
    if target:
        return await _run_crawl_webpage(ctx, target)
    return await _run_original(ctx, tool_name, args)


async def _run_original(ctx, tool_name: str, args: dict) -> str:
    func = _find_tool_func(tool_name)
    if func is None:
        return f"[Middleware] {tool_name} 切换失败：替换工具与原工具均不可用"
    return await func(ctx, **args)


async def _run_browser_extract_links(ctx, args: dict, current_url: str) -> str:
    func = _find_tool_func("browser_extract_links")
    if func is None:
        raise RuntimeError("browser_extract_links tool not registered")
    kwargs: dict = {
        "document_only": True,
        "allowed_domains": urlparse(current_url).hostname or "",
        "include_metadata": True,
        "max_pages": 5,
    }
    for key in ("selector", "pagination_next_selector", "wait_for_selector", "document_domains"):
        if args.get(key):
            kwargs[key] = args[key]
    result = await func(ctx, **kwargs)
    return _label("browser_extract_links", "browser_extract_links", kwargs, result)


async def _run_crawl_webpage(ctx, target_url: str) -> str:
    func = _find_tool_func("crawl_webpage")
    if func is None:
        raise RuntimeError("crawl_webpage tool not registered")
    kwargs: dict = {
        "url": target_url,
        "allowed_domains": urlparse(target_url).hostname or "",
        "max_pages": 5,
    }
    result = await func(ctx, **kwargs)
    return _label("crawl_webpage", "crawl_webpage", kwargs, result)
