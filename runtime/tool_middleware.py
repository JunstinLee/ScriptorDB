from __future__ import annotations

import json
import re
import threading
from typing import Any
from urllib.parse import urlparse

from core.logging_setup import get_logger

logger = get_logger("tool_middleware")

_BLOCKED_TOOLS = {
    "browser_query",
    "browser_get_text",
    "browser_evaluate",
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

# 交互式任务（点击/填写/筛选/测试等）需要低层级 DOM 工具检查页面结构，
# 不属于"文档提取"，命中即豁免，避免把合法排查误拦成 browser_extract_links。
_INTERACTION_KEYWORDS = (
    "点击",
    "填写",
    "输入",
    "选择",
    "选中",
    "筛选",
    "过滤",
    "下拉",
    "测试",
    "切换",
    "click",
    "fill",
    "type",
    "select",
    "filter",
    "dropdown",
    "test",
    "choose",
)

_URL_PATH_SIGNALS = ("filings", "documents", "docs", "download", "archive")

_URL_RE = re.compile(r"https?://[^\s\"'<>，。；）)】\]}]+")

_SWITCH_LABEL = (
    "[Middleware] {tool_name} call intercepted (document-extraction task — low-level browser tools not suitable). "
    "Automatically switched to {replacement} with args: {args}\n"
    "The result is final data — use it directly. If it does not meet the request, explain why to the user, "
    "or use browser_extract_links / crawl_webpage instead.\n\n{result}"
)

_REPEAT_LABEL = (
    "[Middleware] {tool_name} has been intercepted multiple times this turn — do not call it again.\n"
    "For web data, call browser_extract_links (supports document filtering / pagination / domain limits) or "
    "crawl_webpage; if the result does not meet the request, explain why to the user."
)

_NO_PYTHON_LABEL = (
    "[Middleware] python_sandbox_execute intercepted: browser/crawl tool results are already final data, "
    "no Python processing needed. Answer directly from the results; for extra computation, explain the need to the user."
)

_NO_PYTHON_REPEAT_LABEL = (
    "[Middleware] python_sandbox_execute intercepted repeatedly: answer directly from the final browser/crawl tool data, "
    "no Python processing needed."
)

_EMPTY_RESULT_MARKERS = (
    "no links found",
    "no elements found",
    "no items found",
    "link extraction failed",
    "crawl failed",
    "no response",
    "timed out",
    "request timed out",
)

_lock = threading.Lock()
_round_blocks: dict[str, dict[str, int]] = {}
_round_browser_used: set[str] = set()

_MAX_ROUNDS = 1000


def _is_browser_tool(tool_name: str) -> bool:
    return tool_name.startswith("browser_")


def _round_key(ctx) -> str:
    return getattr(ctx, "run_id", None) or "default-round"


def _bump_round_block(round_id: str, tool_name: str) -> int:
    global _round_blocks
    with _lock:
        if len(_round_blocks) > _MAX_ROUNDS:
            _round_blocks = {}
        counters = _round_blocks.setdefault(round_id, {})
        counters[tool_name] = counters.get(tool_name, 0) + 1
        return counters[tool_name]


def _mark_browser_used(round_id: str) -> None:
    with _lock:
        if len(_round_browser_used) > _MAX_ROUNDS:
            _round_browser_used.clear()
        _round_browser_used.add(round_id)


def _browser_launched() -> bool:
    try:
        from browser import get_manager

        return get_manager().page() is not None
    except Exception:
        return False


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
    if any(keyword in blob for keyword in _INTERACTION_KEYWORDS):
        return False
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


def _label(tool_name: str, replacement: str, kwargs: dict, result: Any) -> str:
    if isinstance(result, dict):
        result = json.dumps(result, ensure_ascii=False)
    return _SWITCH_LABEL.format(
        tool_name=tool_name,
        replacement=replacement,
        args=json.dumps(kwargs, ensure_ascii=False),
        result=result,
    )


def _result_is_empty(result: str | dict) -> bool:
    if isinstance(result, dict):
        return not result.get("rows") and not result.get("links")
    low = result.lower()
    return any(marker in low for marker in _EMPTY_RESULT_MARKERS)


def _browser_extract_kwargs(tool_name: str, args: dict, current_url: str) -> dict:
    """Synthesize params for the browser_extract_links switch.

    Only session-derived, harmless params are synthesized (metadata + site
    pagination). Task-constraint params (domain policy, document filter,
    selectors) are inherited from the original call when present — never
    hard-bound to the current page.
    """
    kwargs: dict = {"include_metadata": True, "max_pages": 5, "resolve_redirects": True}
    if tool_name == "browser_extract_links":
        inherit = ("selector", "wait_for_selector", "pagination_next_selector",
                   "allowed_domains", "document_domains", "document_only")
    else:
        inherit = ()
    for key in inherit:
        if args.get(key):
            kwargs[key] = args[key]
    return kwargs


async def evaluate_call(ctx, tool_name: str) -> str:
    """Decide whether a tool call may execute.

    Returns one of:
    - "allow":      execute normally
    - "switch":     block and auto-switch to a more appropriate tool
    - "repeat":     block; same tool already blocked this round — do not run anything
    - "no-python":  block; browser control task forbids python_sandbox_execute

    Fails open: any uncertainty → "allow".
    """
    if ctx is None or getattr(ctx, "deps", None) is None:
        return "allow"
    round_id = _round_key(ctx)
    if _is_browser_tool(tool_name):
        _mark_browser_used(round_id)

    if tool_name == "python_sandbox_execute":
        if round_id in _round_browser_used or _browser_launched():
            logger.info("tool middleware: blocking python_sandbox_execute — browser control active (round %s)", round_id)
            if _bump_round_block(round_id, tool_name) >= 2:
                return "no-python-repeat"
            return "no-python"

    if tool_name not in _BLOCKED_TOOLS:
        return "allow"
    if not _is_document_discovery(ctx):
        return "allow"
    if not (_target_url_from_prompt(ctx) or _current_page_url()):
        return "allow"
    count = _bump_round_block(round_id, tool_name)
    logger.info("tool middleware: blocking %s (round block #%d) — document discovery detected", tool_name, count)
    if count >= 2:
        return "repeat"
    return "switch"


async def execute_switch(ctx, tool_name: str, args: dict, decision: str) -> str:
    """Execute the middleware action for a blocked tool call."""
    if decision == "no-python":
        return _NO_PYTHON_LABEL
    if decision == "no-python-repeat":
        return _NO_PYTHON_REPEAT_LABEL
    if decision == "repeat":
        return _REPEAT_LABEL.format(tool_name=tool_name)

    current = _current_page_url()
    target = _target_url_from_prompt(ctx)

    if current and (not target or _same_domain(current, target)):
        replacement = "browser_extract_links"
        kwargs = _browser_extract_kwargs(tool_name, args, current)
    elif target:
        replacement = "crawl_webpage"
        kwargs = {
            "url": target,
            "max_pages": 5,
        }
    else:
        return await _run_original(ctx, tool_name, args)

    func = _find_tool_func(replacement)
    if func is None:
        return await _run_original(ctx, tool_name, args)

    inner = await func(ctx, **kwargs)
    if _result_is_empty(inner):
        logger.info(
            "tool middleware: switch result empty for %s (round %s) — falling back to original call",
            tool_name,
            _round_key(ctx),
        )
        original = await _run_original(ctx, tool_name, args)
        return (
            f"[Middleware] {tool_name} intercepted and switched to {replacement}, but the result was empty — "
            f"fell back to the original call.\n\n{original}"
        )
    return _label(tool_name, replacement, kwargs, inner)


async def _run_original(ctx, tool_name: str, args: dict) -> str:
    func = _find_tool_func(tool_name)
    if func is None:
        return f"[Middleware] {tool_name} switch failed: neither the replacement nor the original tool is available"
    return await func(ctx, **args)
