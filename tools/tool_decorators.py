from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import Any

from pydantic_ai import Tool

from core.logging_setup import get_logger

logger = get_logger("tools.tool_decorators")


def _wrap_browser_tool(
    func: Callable[..., Any],
    name: str,
    timeout: int = 15,
) -> Callable[..., Any]:
    """Wrap browser-category tools (and python_sandbox_execute) with the middleware.

    The middleware may block a low-level browser call in document-discovery
    contexts and auto-switch to a more appropriate tool (browser_extract_links
    / crawl_webpage), returning its labeled result; it also blocks
    python_sandbox_execute once a task involves browser control. `functools.wraps`
    keeps the original signature so the tool schema is unchanged.

    Tool execution is wrapped in `asyncio.wait_for`: on timeout it returns an
    explicit error string instead of letting pydantic-ai produce an empty
    ModelRequest (empty request leaves a tool call without a response, which
    model APIs reject on history replay).
    """

    @functools.wraps(func)
    async def wrapped(ctx, *args, **kwargs):
        # 兜底：任何工具级未捕获异常（如导航中页面上下文被销毁）都转为
        # 失败字符串交还给模型，绝不向上冒泡终止整个 run。
        try:
            async def call_original():
                if inspect.iscoroutinefunction(func):
                    return await func(ctx, *args, **kwargs)
                # sync 工具（如 python_sandbox_execute 返回 ToolResult）不能 await，
                # 丢线程执行避免阻塞事件循环
                return await asyncio.to_thread(func, ctx, *args, **kwargs)

            async def run_with_timeout():
                try:
                    return await asyncio.wait_for(call_original(), timeout=timeout)
                except asyncio.TimeoutError:
                    return (
                        f"失败: 工具执行超时（{timeout} 秒），操作未完成，"
                        "请重试或改用其他方式。"
                    )

            enabled = bool(getattr(getattr(ctx, "deps", None), "browser_middleware_enabled", True))
            if not enabled:
                return await run_with_timeout()
            from runtime.tool_middleware import evaluate_call, execute_switch

            decision = await evaluate_call(ctx, name)
            if decision == "allow":
                return await run_with_timeout()
            return await execute_switch(ctx, name, kwargs, decision)
        except Exception as e:
            logger.exception("tool %s raised uncaught %s: %s", name, type(e).__name__, e)
            return (
                f"失败: 工具执行异常（{type(e).__name__}: {e}），"
                "请重试或改用其他方式。"
            )

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
        tool_timeout = self.timeout
        if self.category == "browser" or self.name == "python_sandbox_execute":
            func = _wrap_browser_tool(func, self.name, timeout=self.timeout)
            # 超时由 wrapper 统一管理：pydantic-ai 框架层超时会生成空的
            # ModelRequest，导致工具调用没有响应，历史重放被模型 API 拒绝。
            tool_timeout = None
        return Tool(
            func,
            takes_ctx=True,
            name=self.name,
            timeout=tool_timeout,
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
