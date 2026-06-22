from __future__ import annotations

import asyncio
import json as json_mod
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from agents.db_agent import get_agent
from config.canonical_models import get_canonical_by_slug
from config.models import fuzzy_match_model, resolve_canonical_slug
from config.settings import Settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    TextPartDelta,
    UserPromptPart,
)
from tools.tool_result import ToolResult


def _sse_lines(data: str) -> str:
    lines = data.split("\n")
    return "\n".join(lines)


def _sse_event(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {_sse_lines(_sse_encode_json(payload))}\n\n"


def _sse_encode_json(obj: dict) -> str:
    return json_mod.dumps(obj, ensure_ascii=False, default=str)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_tool_start_times: dict[str, float] = {}


async def stream_agent_response(
    prompt: str,
    message_history: list[ModelMessage],
    settings: Settings,
    model: str | None = None,
    provider: str | None = None,
    agent: Agent[Settings] | None = None,
    run_collector: dict[str, Any] | None = None,
    new_messages_collector: list[ModelMessage] | None = None,
) -> AsyncIterator[str]:
    if provider:
        settings.llm_provider = provider
    if model:
        matched = fuzzy_match_model(settings.llm_provider, model)
        if matched:
            settings.llm_model = matched

    agent = agent or get_agent(model, provider)
    full_output = ""
    run_id = uuid.uuid4().hex[:12]
    trace_step = 0
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    if run_collector is not None:
        run_collector.update({
            "run_id": run_id,
            "status": "running",
            "tool_invocations": [],
            "final_output": "",
            "started_at": _utc_now_iso(),
            "ended_at": None,
            "error_message": None,
        })

    yield _sse_event("run_start", {
        "type": "run_start",
        "run_id": run_id,
        "timestamp": _utc_now_iso(),
    })

    async def event_stream_handler(ctx: RunContext[Settings], events: Any) -> None:
        nonlocal full_output, trace_step
        try:
            async for event in events:
                if isinstance(event, FunctionToolCallEvent):
                    call_id = event.part.tool_call_id
                    _tool_start_times[call_id] = time.monotonic()
                    args = event.part.args
                    if isinstance(args, str):
                        try:
                            args = json_mod.loads(args)
                        except json_mod.JSONDecodeError:
                            args = {"raw": args}
                    args_dict = args if isinstance(args, dict) else {"raw": str(args)}
                    if run_collector is not None:
                        run_collector["tool_invocations"].append({
                            "call_id": call_id,
                            "tool_name": event.part.tool_name,
                            "args": args_dict,
                            "status": "running",
                            "started_at": _utc_now_iso(),
                        })
                    await queue.put(_sse_event("tool_call", {
                        "type": "tool_call",
                        "run_id": run_id,
                        "call_id": call_id,
                        "tool_name": event.part.tool_name,
                        "args": args_dict,
                        "timestamp": _utc_now_iso(),
                    }))

                    trace_step += 1
                    await queue.put(_sse_event("trace", {
                        "type": "trace",
                        "run_id": run_id,
                        "step": trace_step,
                        "message": f"调用工具 {event.part.tool_name}",
                        "timestamp": _utc_now_iso(),
                    }))

                elif isinstance(event, FunctionToolResultEvent):
                    call_id = event.part.tool_call_id if event.part else "unknown"
                    tool_name = event.part.tool_name if event.part else "unknown"
                    start = _tool_start_times.pop(call_id, None)
                    duration_ms = (
                        int((time.monotonic() - start) * 1000) if start else None
                    )

                    success = True
                    output = None
                    error_code = None
                    content = event.part.content if event.part else None
                    if isinstance(content, ToolResult):
                        success = content.success
                        output = content.output
                        if content.error:
                            error_code = content.error.category
                            output = content.error.message
                    elif isinstance(content, str):
                        output = content

                    if run_collector is not None:
                        for inv in run_collector["tool_invocations"]:
                            if inv["call_id"] == call_id:
                                inv["status"] = "success" if success else "error"
                                inv["output"] = output
                                inv["error_code"] = error_code
                                inv["duration_ms"] = duration_ms
                                inv["ended_at"] = _utc_now_iso()
                                break

                    await queue.put(_sse_event("tool_result", {
                        "type": "tool_result",
                        "run_id": run_id,
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "success": success,
                        "output": output,
                        "error_code": error_code,
                        "duration_ms": duration_ms,
                        "timestamp": _utc_now_iso(),
                    }))

                    trace_step += 1
                    await queue.put(_sse_event("trace", {
                        "type": "trace",
                        "run_id": run_id,
                        "step": trace_step,
                        "message": f"工具 {tool_name} 执行{'成功' if success else '失败'}: {output or error_code or ''}",
                        "timestamp": _utc_now_iso(),
                    }))

                else:
                    event_str = str(event)
                    if "TextPartDelta" in event_str or "content_delta" in event_str:
                        if hasattr(event, "delta") and isinstance(event.delta, TextPartDelta):
                            content_delta = event.delta.content_delta
                            if content_delta:
                                full_output += content_delta
                                if run_collector is not None:
                                    run_collector["final_output"] = full_output
                                await queue.put(_sse_event("text_delta", {
                                    "type": "text_delta",
                                    "run_id": run_id,
                                    "delta": content_delta,
                                }))

        finally:
            await queue.put(None)

    async def run_agent() -> Any:
        return await agent.run(
            prompt,
            message_history=message_history if message_history else None,
            deps=settings,
            event_stream_handler=event_stream_handler,
        )

    run_task = asyncio.create_task(run_agent())

    try:
        while True:
            sse = await queue.get()
            if sse is None:
                break
            yield sse

        result = await run_task

        if not full_output and result.output:
            full_output = str(result.output)

        if new_messages_collector is not None:
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
            new_messages_collector.extend(new_messages)

        canonical_slug = None
        display_name = None
        if settings.llm_model:
            slug = resolve_canonical_slug(settings.llm_provider, settings.llm_model)
            if slug:
                canonical_slug = slug
                c = get_canonical_by_slug(slug)
                if c:
                    display_name = c.display_name

        if run_collector is not None:
            run_collector.update({
                "status": "completed",
                "final_output": full_output,
                "ended_at": _utc_now_iso(),
            })

        yield "data: [DONE]\n\n"
        yield _sse_event("metadata", {
            "type": "metadata",
            "run_id": run_id,
            "full_output": full_output,
            "canonical_slug": canonical_slug,
            "display_name": display_name,
            "provider_specific_id": settings.llm_model,
        })
        yield _sse_event("run_end", {
            "type": "run_end",
            "run_id": run_id,
            "timestamp": _utc_now_iso(),
        })

    except Exception as e:
        if run_collector is not None:
            run_collector.update({
                "status": "error",
                "error_message": str(e),
                "ended_at": _utc_now_iso(),
            })
        yield _sse_event("error", {
            "type": "error",
            "run_id": run_id,
            "message": str(e),
            "error_id": uuid.uuid4().hex[:12],
        })
        yield _sse_event("run_end", {
            "type": "run_end",
            "run_id": run_id,
            "timestamp": _utc_now_iso(),
        })
    finally:
        _tool_start_times.clear()
