"""被拦截调用的处置：执行改派或返回对应文案。

``execute_switch`` 只负责「决策 → 动作」映射，判定在 registry/policies。
"""

from __future__ import annotations

import json
from typing import Any

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.labels import (
    _EMPTY_RESULT_MARKERS,
    _FILTER_LABEL,
    _FILTER_REPEAT_LABEL,
    _FIND_REPEAT_LABEL,
    _NO_PYTHON_LABEL,
    _NO_PYTHON_REPEAT_LABEL,
    _SWITCH_LABEL,
    _UI_PROBE_LABEL,
    _UI_PROBE_REPEAT_LABEL,
)
from runtime.middleware_probe import (
    _current_page_url,
    _same_domain,
    _target_url_from_prompt,
)
from schemas import ToolResult

logger = get_logger("tool_middleware")


def _label(tool_name: str, replacement: str, kwargs: dict, result: Any) -> str:
    if isinstance(result, dict):
        result = json.dumps(result, ensure_ascii=False)
    return _SWITCH_LABEL.format(
        tool_name=tool_name,
        replacement=replacement,
        args=json.dumps(kwargs, ensure_ascii=False),
        result=result,
    )


def _result_is_empty(result: Any) -> bool:
    if isinstance(result, ToolResult):
        return not result.success
    if isinstance(result, dict):
        return not result.get("rows") and not result.get("links")
    low = str(result).lower()
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


async def _run_original(ctx, tool_name: str, args: dict) -> str:
    func = ctxmod._find_tool_func(tool_name)
    if func is None:
        return f"[Middleware] {tool_name} switch failed: neither the replacement nor the original tool is available"
    return await func(ctx, **args)


async def execute_switch(ctx, tool_name: str, args: dict, decision: str) -> str:
    """Execute the middleware action for a blocked tool call."""
    if decision == "no-python":
        return _NO_PYTHON_LABEL
    if decision == "no-python-repeat":
        return _NO_PYTHON_REPEAT_LABEL
    if decision == "filter-block":
        return _FILTER_LABEL.format(tool_name=tool_name)
    if decision == "filter-repeat":
        return _FILTER_REPEAT_LABEL.format(tool_name=tool_name)
    if decision == "ui-probe-block":
        return _UI_PROBE_LABEL.format(tool_name=tool_name)
    if decision == "ui-probe-repeat":
        return _UI_PROBE_REPEAT_LABEL.format(tool_name=tool_name)
    if decision == "find-repeat":
        return _FIND_REPEAT_LABEL

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

    func = ctxmod._find_tool_func(replacement)
    if func is None:
        return await _run_original(ctx, tool_name, args)

    inner = await func(ctx, **kwargs)
    if _result_is_empty(inner):
        logger.info(
            "tool middleware: switch result empty for %s (round %s) — falling back to original call",
            tool_name,
            ctxmod._round_key(ctx),
        )
        original = await _run_original(ctx, tool_name, args)
        return (
            f"[Middleware] {tool_name} intercepted and switched to {replacement}, but the result was empty — "
            f"fell back to the original call.\n\n{original}"
        )
    return _label(tool_name, replacement, kwargs, inner)
