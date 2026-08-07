from __future__ import annotations

import json
import re
import threading
from urllib.parse import urlparse

from logging_setup import get_logger

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

_URL_PATH_SIGNALS = ("filings", "documents", "docs", "download", "archive")

_URL_RE = re.compile(r"https?://[^\s\"'<>，。；）)】\]}]+")

_SWITCH_LABEL = (
    "[Middleware] {tool_name} 调用被拦截（当前任务属于文档提取场景，低级别浏览器工具不适合），"
    "已自动切换执行 {replacement}，参数：{args}\n"
    "返回结果即最终数据，请直接使用。如结果不满足需求，请直接向用户说明原因，"
    "或改用 browser_extract_links / crawl_webpage。\n\n{result}"
)

_REPEAT_LABEL = (
    "[Middleware] {tool_name} 在本轮任务中已多次被拦截，请勿再次调用该工具。\n"
    "如需网页数据，请直接调用 browser_extract_links（支持文档过滤/翻页/域名限制）或 "
    "crawl_webpage；如结果不满足需求，请直接向用户说明原因。"
)

_NO_PYTHON_LABEL = (
    "[Middleware] run_python_code 被拦截：当前任务已涉及浏览器控制，禁止使用 Python 代码。\n"
    "工具返回结果（含 [Middleware] 标注结果）即最终数据，请直接使用；"
    "如需计算、分析或格式化，请说明需求，不要用 run_python_code 处理网页数据。"
)

_NO_PYTHON_REPEAT_LABEL = (
    "[Middleware] run_python_code 已多次被拦截：当前任务涉及浏览器控制，禁止使用 Python。\n"
    "请直接基于工具已返回的最终数据输出答案，禁止再次调用 run_python_code。"
)

_EMPTY_RESULT_MARKERS = (
    "no links found",
    "no elements found",
    "no items found",
    "link extraction failed",
    "抓取失败",
    "no response",
    "timed out",
    "请求超时",
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


def _result_is_empty(result: str) -> bool:
    low = result.lower()
    return any(marker in low for marker in _EMPTY_RESULT_MARKERS)


def _browser_extract_kwargs(tool_name: str, args: dict, current_url: str) -> dict:
    """Synthesize params for the browser_extract_links switch.

    Only session-derived, harmless params are synthesized (metadata + site
    pagination). Task-constraint params (domain policy, document filter,
    selectors) are inherited from the original call when present — never
    hard-bound to the current page.
    """
    kwargs: dict = {"include_metadata": True, "max_pages": 5}
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
    - "no-python":  block; browser control task forbids run_python_code

    Fails open: any uncertainty → "allow".
    """
    if ctx is None or getattr(ctx, "deps", None) is None:
        return "allow"
    round_id = _round_key(ctx)
    if _is_browser_tool(tool_name):
        _mark_browser_used(round_id)

    if tool_name == "run_python_code":
        if round_id in _round_browser_used or _browser_launched():
            logger.info("tool middleware: blocking run_python_code — browser control active (round %s)", round_id)
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
            f"[Middleware] {tool_name} 被拦截，已自动切换执行 {replacement}，但结果为空，"
            f"已回退执行原调用。\n\n{original}"
        )
    return _label(tool_name, replacement, kwargs, inner)


async def _run_original(ctx, tool_name: str, args: dict) -> str:
    func = _find_tool_func(tool_name)
    if func is None:
        return f"[Middleware] {tool_name} 切换失败：替换工具与原工具均不可用"
    return await func(ctx, **args)
