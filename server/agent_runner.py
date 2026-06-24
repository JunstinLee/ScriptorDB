from __future__ import annotations

import asyncio
import json as json_mod
import traceback
import uuid
from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    TextPartDelta,
    UserPromptPart,
)

from agents.db_agent import get_agent
from config.app_config import AppConfig
from config.models import fuzzy_match_model
from tools.tool_result import ToolResult

from server.run_tracker import RunTracker, utc_now_iso


async def run_agent_stream(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Agent[AppConfig] | None = None,
    tracker: RunTracker | None = None,
) -> AsyncIterator[dict]:
    """纯编排层：启动 agent.run()，通过 asyncio.Queue 收集事件，产出标准化 dict 事件。

    不再产出 SSE 字符串，由 streaming 层负责包装。

    事件类型：
    - run_start, run_end, error, metadata
    - tool_call, tool_result
    - text_delta
    - trace
    """
    if provider:
        config.llm_provider = provider
    if model:
        matched = fuzzy_match_model(config.llm_provider, model)
        if matched:
            config.llm_model = matched

    agent = agent or get_agent(model, provider, config=config)
    full_output = ""
    run_id = tracker.run_id if tracker else ""
    trace_step = 0
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    local_tracker = tracker or RunTracker()

    yield {
        "type": "run_start",
        "run_id": local_tracker.run_id,
        "timestamp": utc_now_iso(),
    }

    async def event_stream_handler(ctx: RunContext[AppConfig], events: Any) -> None:
        nonlocal full_output, trace_step
        try:
            async for event in events:
                if isinstance(event, FunctionToolCallEvent):
                    call_id = event.part.tool_call_id
                    local_tracker.start_tool(call_id)
                    args = event.part.args
                    if isinstance(args, str):
                        try:
                            args = json_mod.loads(args)
                        except json_mod.JSONDecodeError:
                            args = {"raw": args}
                    args_dict = args if isinstance(args, dict) else {"raw": str(args)}
                    local_tracker.add_tool_invocation(
                        call_id, event.part.tool_name, args_dict
                    )
                    await queue.put({
                        "type": "tool_call",
                        "run_id": local_tracker.run_id,
                        "call_id": call_id,
                        "tool_name": event.part.tool_name,
                        "args": args_dict,
                        "timestamp": utc_now_iso(),
                    })

                    trace_step += 1
                    await queue.put({
                        "type": "trace",
                        "run_id": local_tracker.run_id,
                        "step": trace_step,
                        "message": f"调用工具 {event.part.tool_name}",
                        "timestamp": utc_now_iso(),
                    })

                elif isinstance(event, FunctionToolResultEvent):
                    call_id = event.part.tool_call_id if event.part else "unknown"
                    tool_name = event.part.tool_name if event.part else "unknown"
                    duration_ms = local_tracker.tool_duration_ms(call_id)

                    success = True
                    output: Any = None
                    error_code: str | None = None
                    content = event.part.content if event.part else None
                    if isinstance(content, ToolResult):
                        success = content.success
                        output = content.output
                        if content.error:
                            error_code = content.error.category
                            output = content.error.message
                    elif isinstance(content, str):
                        output = content

                    local_tracker.complete_tool(
                        call_id, success, output, error_code, duration_ms
                    )

                    await queue.put({
                        "type": "tool_result",
                        "run_id": local_tracker.run_id,
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "success": success,
                        "output": output,
                        "error_code": error_code,
                        "duration_ms": duration_ms,
                        "timestamp": utc_now_iso(),
                    })

                    trace_step += 1
                    await queue.put({
                        "type": "trace",
                        "run_id": local_tracker.run_id,
                        "step": trace_step,
                        "message": f"工具 {tool_name} 执行{'成功' if success else '失败'}: {output or error_code or ''}",
                        "timestamp": utc_now_iso(),
                    })

                else:
                    event_str = str(event)
                    if "TextPartDelta" in event_str or "content_delta" in event_str:
                        if hasattr(event, "delta") and isinstance(event.delta, TextPartDelta):
                            content_delta = event.delta.content_delta
                            if content_delta:
                                full_output += content_delta
                                local_tracker.append_text(content_delta)
                                await queue.put({
                                    "type": "text_delta",
                                    "run_id": local_tracker.run_id,
                                    "delta": content_delta,
                                })

        finally:
            await queue.put(None)

    async def run_agent() -> Any:
        return await agent.run(
            prompt,
            message_history=message_history if message_history else None,
            deps=config,
            event_stream_handler=event_stream_handler,
        )

    run_task = asyncio.create_task(run_agent())

    try:
        while True:
            ev = await queue.get()
            if ev is None:
                break
            yield ev

        result = await run_task

        if not full_output and result.output:
            full_output = str(result.output)
            local_tracker.final_output = full_output

        new_messages = result.new_messages()
        if (
            new_messages
            and isinstance(new_messages[0], ModelRequest)
            and all(
                isinstance(p, UserPromptPart)
                for p in new_messages[0].parts
            )
        ):
            new_messages = new_messages[1:]

        yield {
            "type": "new_messages",
            "run_id": local_tracker.run_id,
            "messages": new_messages,
        }

        local_tracker.finish()
        yield {
            "type": "metadata",
            "run_id": local_tracker.run_id,
            "full_output": full_output,
        }
        yield {
            "type": "run_end",
            "run_id": local_tracker.run_id,
            "timestamp": utc_now_iso(),
        }
    except Exception as e:
        error_id = uuid.uuid4().hex[:12]
        from tools.errors import _get_error_logger
        logger = _get_error_logger()
        logger.error(
            "[%s] run_error exception=%s\n%s",
            error_id,
            repr(e),
            traceback.format_exc(),
        )
        local_tracker.fail(str(e))
        yield {
            "type": "error",
            "run_id": local_tracker.run_id,
            "message": f"运行失败（ID: {error_id}），请联系管理员",
            "error_id": error_id,
        }
        yield {
            "type": "run_end",
            "run_id": local_tracker.run_id,
            "timestamp": utc_now_iso(),
        }
