from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    TextPartDelta,
)

from logging_setup import get_logger
from server.runner.events import (
    normalize_tool_content,
    parse_tool_args,
    text_delta_event,
    tool_call_event,
    tool_result_event,
    trace_event,
)
from server.runner.takeover_hook import AfterToolContext, BrowserTakeoverHook

logger = get_logger("agent_runner.translator")


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
        config: Any,
        checkpoint_id: str,
        prompt: str,
        message_history: list,
        takeover_hook: BrowserTakeoverHook | None = None,
    ) -> None:
        self._queue = queue
        self._tracker = tracker
        self._config = config
        self._checkpoint_id = checkpoint_id
        self._prompt = prompt
        self._message_history = message_history
        self._takeover_hook = takeover_hook or BrowserTakeoverHook()

        # Mutable run state shared with the lifecycle layer.
        self.full_output = ""
        self.trace_step = 0
        self.handler_calls = 0
        self.tool_parts: list[Any] = []

    async def handle(self, ctx: RunContext[Any], events: Any) -> None:
        self.handler_calls += 1
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                await self._handle_tool_call(event)
            elif isinstance(event, FunctionToolResultEvent):
                await self._handle_tool_result(event)
            else:
                await self._handle_text_delta(event)

    async def _handle_tool_call(self, event: FunctionToolCallEvent) -> None:
        self.tool_parts.append(event.part)
        call_id = event.part.tool_call_id
        self._tracker.start_tool(call_id)
        args_dict = parse_tool_args(event.part.args)
        self._tracker.add_tool_invocation(call_id, event.part.tool_name, args_dict)
        await self._queue.put(tool_call_event(
            run_id=self._tracker.run_id,
            call_id=call_id,
            tool_name=event.part.tool_name,
            args=args_dict,
        ))
        self.trace_step += 1
        await self._queue.put(trace_event(
            run_id=self._tracker.run_id,
            step=self.trace_step,
            message=f"调用工具 {event.part.tool_name}",
        ))

    async def _handle_tool_result(self, event: FunctionToolResultEvent) -> None:
        self.tool_parts.append(event.part)
        call_id = event.part.tool_call_id if event.part else "unknown"
        tool_name = event.part.tool_name if event.part else "unknown"
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

        await self._takeover_hook.after_tool_result(AfterToolContext(
            queue=self._queue,
            tool_name=tool_name,
            success=success,
            session_id=getattr(self._config, "chat_session_id", "") or "",
            run_id=self._tracker.run_id,
            checkpoint_id=self._checkpoint_id,
            prompt=self._prompt,
            message_history=self._message_history,
            tool_parts=self.tool_parts,
            tool_invocations=self._tracker.tool_invocations,
            final_output=self.full_output,
        ))

        self.trace_step += 1
        await self._queue.put(trace_event(
            run_id=self._tracker.run_id,
            step=self.trace_step,
            message=f"工具 {tool_name} 执行{'成功' if success else '失败'}: {output or error_code or ''}",
        ))

    async def _handle_text_delta(self, event: Any) -> None:
        event_str = str(event)
        if "TextPartDelta" in event_str or "content_delta" in event_str:
            if hasattr(event, "delta") and isinstance(event.delta, TextPartDelta):
                content_delta = event.delta.content_delta
                if content_delta:
                    self.full_output += content_delta
                    self._tracker.append_text(content_delta)
                    await self._queue.put(text_delta_event(
                        run_id=self._tracker.run_id,
                        delta=content_delta,
                    ))
