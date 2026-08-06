from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from pydantic_ai import Tool


def _wrap_browser_tool(func: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Wrap browser-category tools with the tool-call middleware.

    The middleware may block a low-level browser call in document-discovery
    contexts and auto-switch to a more appropriate tool (browser_extract_links
    / crawl_webpage), returning its labeled result. `functools.wraps` keeps the
    original signature so the tool schema is unchanged.
    """

    @functools.wraps(func)
    async def wrapped(ctx, *args, **kwargs):
        enabled = bool(getattr(getattr(ctx, "deps", None), "browser_middleware_enabled", True))
        if not enabled:
            return await func(ctx, *args, **kwargs)
        from services.tool_middleware import evaluate_call, execute_switch

        decision = await evaluate_call(ctx, name)
        if decision == "switch":
            return await execute_switch(ctx, name, kwargs)
        return await func(ctx, *args, **kwargs)

    return wrapped


class ToolDef:
    __slots__ = (
        "func",
        "name",
        "category",
        "timeout",
        "max_retries",
        "requires_approval",
        "validator",
        "sequential",
    )

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        category: str = "read",
        timeout: int = 10,
        max_retries: int = 1,
        requires_approval: bool = False,
        validator: Callable[..., Any] | None = None,
        sequential: bool = False,
    ):
        self.func = func
        self.name = name or func.__name__
        self.category = category
        self.timeout = timeout
        self.max_retries = max_retries
        self.requires_approval = requires_approval
        self.validator = validator
        self.sequential = sequential

    def to_tool(self) -> Tool:
        func = self.func
        if self.category == "browser":
            func = _wrap_browser_tool(func, self.name)
        return Tool(
            func,
            takes_ctx=True,
            name=self.name,
            timeout=self.timeout,
            max_retries=self.max_retries,
            requires_approval=self.requires_approval,
            args_validator=self.validator,
            sequential=self.sequential,
            include_return_schema=True,
        )


_tool_defs: list[ToolDef] = []


def get_all_tool_defs() -> list[ToolDef]:
    return list(_tool_defs)


def db_tool(
    *,
    name: str | None = None,
    category: str = "read",
    timeout: int = 10,
    max_retries: int = 1,
    requires_approval: bool = False,
    validator: Callable[..., Any] | None = None,
    sequential: bool = False,
):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        _tool_defs.append(
            ToolDef(
                func,
                name=name,
                category=category,
                timeout=timeout,
                max_retries=max_retries,
                requires_approval=requires_approval,
                validator=validator,
                sequential=sequential,
            )
        )
        return func

    return decorator
