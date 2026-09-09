from __future__ import annotations

import asyncio
import copy
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
)

from core.logging_setup import get_logger
from runtime.redact import redact
from runtime.runner.events import (
    normalize_tool_content,
    parse_tool_args,
    text_delta_event,
    tool_call_event,
    tool_result_event,
    trace_event,
)
from runtime.runner.errors import SiteUnavailableError
from runtime.runner.takeover_hook import (
    AfterToolContext,
    BrowserTakeoverHook,
    RunPauseState,
)
from runtime.site_unavailable import detect_site_unavailable

logger = get_logger("agent_runner.translator")

# 工具调用参数里承载可能含系统密码文本的字段（按工具名）。
# 实时层（tracker/SSE/tool_parts）仅对这两个工具的参数做脱敏副本，
# 其余工具无系统密码入口，保持原样。
_SENSITIVE_TEXT_FIELDS = {
    "browser_fill": "text",
    "browser_evaluate": "js",
}


def _redact_clean_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """返回 args 的脱敏副本（browser_fill.text / browser_evaluate.js 过 redact）。"""
    field = _SENSITIVE_TEXT_FIELDS.get(tool_name)
    if field is None or not isinstance(args.get(field), str):
        return args
    clean = dict(args)
    clean[field] = redact(clean[field])
    return clean


def _redact_clean_part(part: ToolCallPart) -> ToolCallPart:
    """返回 ToolCallPart 的脱敏副本：args 字段值（str 或 dict）过 redact。"""
    field = _SENSITIVE_TEXT_FIELDS.get(part.tool_name)
    if field is None:
        return part
    if isinstance(part.args, str):
        clean = copy.deepcopy(part)
        clean.args = redact(part.args)  # type: ignore[union-attr]
        return clean
    if isinstance(part.args, dict):
        args = dict(part.args)
        if isinstance(args.get(field), str):
            args[field] = redact(args[field])
        clean = copy.deepcopy(part)
        clean.args = args  # type: ignore[union-attr]
        return clean
    return part


class EventTranslator:
    """Translates pydantic-ai run events into application dict events on the queue.

    Dependencies (queue, tracker, takeover hook) are injected so the translator
    can be unit-tested without a live agent run or browser.
    """

    def __init__(
        self,
        *,
        queue: asyncio.Queue[dict],
        tracker: Any,
        checkpoint_id: str,
        prompt: str,
        message_history: list,
        takeover_hook: BrowserTakeoverHook | None = None,
        pause: RunPauseState | None = None,
        session_id: str = "",
    ) -> None:
        self._queue = queue
        self._tracker = tracker
        self._session_id = session_id
        self._checkpoint_id = checkpoint_id
        self._prompt = prompt
        self._message_history = message_history
        self._takeover_hook = takeover_hook or BrowserTakeoverHook()
        self._pause = pause

        # Mutable run state shared with the lifecycle layer.
        self.trace_step = 0
        self.handler_calls = 0
        self.tool_parts: list[Any] = []

    async def handle(self, ctx: RunContext[Any], events: Any) -> None:
        self.handler_calls += 1
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                await self._handle_tool_call(ctx, event)
            elif isinstance(event, FunctionToolResultEvent):
                await self._handle_tool_result(ctx, event)
            elif isinstance(event, PartStartEvent):
                await self._handle_part_start(event)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                await self._handle_text_delta(event.delta)
            else:
                logger.warning("unhandled run event type: %s", type(event).__name__)

    async def _handle_part_start(self, event: PartStartEvent) -> None:
        part = event.part
        if not isinstance(part, TextPart) or not part.content:
            return
        self._tracker.append_text(part.content)
        await self._queue.put(text_delta_event(
            run_id=self._tracker.run_id,
            delta=part.content,
        ))

    async def _handle_tool_call(
        self, ctx: RunContext[Any], event: FunctionToolCallEvent
    ) -> None:
        # 敏感工具（browser_fill/browser_evaluate）参数可能携带系统密码：
        # tracker 日志/SSE/tool_parts 只收脱敏副本；原始 part 不改动
        # （内存消息原样回放给模型）。
        part = event.part
        if part.tool_name in _SENSITIVE_TEXT_FIELDS:
            part = _redact_clean_part(part)
        args_dict = parse_tool_args(part.args)
        clean_args = _redact_clean_args(part.tool_name, args_dict)
        self.tool_parts.append(part)
        call_id = part.tool_call_id
        self._tracker.start_tool(call_id)
        self._tracker.add_tool_invocation(call_id, part.tool_name, clean_args)
        await self._queue.put(tool_call_event(
            run_id=self._tracker.run_id,
            call_id=call_id,
            tool_name=part.tool_name,
            args=clean_args,
        ))
        self.trace_step += 1
        await self._queue.put(trace_event(
            run_id=self._tracker.run_id,
            step=self.trace_step,
            message=f"调用工具 {part.tool_name}",
        ))

    async def _handle_tool_result(
        self, ctx: RunContext[Any], event: FunctionToolResultEvent
    ) -> None:
        self.tool_parts.append(event.part)
        call_id = event.part.tool_call_id if event.part else "unknown"
        tool_name = (event.part.tool_name if event.part else None) or "unknown"
        duration_ms = self._tracker.tool_duration_ms(call_id)
        content = event.part.content if event.part else None
        success, output, error_code, data = normalize_tool_content(content)

        logger.info(
            "tool_result_event run_id=%s call_id=%s tool=%s content_type=%s "
            "success=%s output_type=%s data_type=%s",
            self._tracker.run_id, call_id, tool_name,
            type(content).__name__ if content is not None else "None",
            success,
            type(output).__name__ if output is not None else "None",
            type(data).__name__ if data is not None else "None",
        )
        self._tracker.complete_tool(
            call_id, success, output, error_code, duration_ms, data=data
        )

        await self._queue.put(tool_result_event(
            run_id=self._tracker.run_id,
            call_id=call_id,
            tool_name=tool_name,
            success=success,
            output=output,
            error_code=error_code,
            duration_ms=duration_ms,
            data=data,
        ))

        # 站点级不可用(网关/DNS/连接失败)是确定性中止信号:失败结果已完整
        # 入队展示,raise 终止本次 run,不让模型继续重试或换方法。置于人工
        # 接管 hook 之前:站点已死时中止优先于登录/接管检测。
        detail = detect_site_unavailable(tool_name, content)
        if detail:
            logger.warning(
                "site unavailable detected tool=%s detail=%s",
                tool_name, detail,
            )
            raise SiteUnavailableError(detail)

        await self._takeover_hook.after_tool_result(AfterToolContext(
            queue=self._queue,
            tool_name=tool_name,
            success=success,
            session_id=self._session_id,
            run_id=self._tracker.run_id,
            checkpoint_id=self._checkpoint_id,
            prompt=self._prompt,
            message_history=self._message_history,
            tool_parts=self.tool_parts,
            tool_invocations=self._tracker.tool_invocations,
            final_output=self._tracker.final_output,
            ctx=ctx,
            pause=self._pause,
        ))

        self.trace_step += 1
        await self._queue.put(trace_event(
            run_id=self._tracker.run_id,
            step=self.trace_step,
            message=f"工具 {tool_name} 执行{'成功' if success else '失败'}: {output or error_code or ''}",
        ))

    async def _handle_text_delta(self, delta: TextPartDelta) -> None:
        content_delta = delta.content_delta
        if content_delta:
            self._tracker.append_text(content_delta)
            await self._queue.put(text_delta_event(
                run_id=self._tracker.run_id,
                delta=content_delta,
            ))
