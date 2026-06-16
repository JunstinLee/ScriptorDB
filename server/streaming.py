from __future__ import annotations

import json as json_mod
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from agents.db_agent import get_agent
from config.canonical_models import get_canonical_by_slug
from config.models import fuzzy_match_model, resolve_canonical_slug
from config.settings import Settings
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPartDelta,
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
    step_counter = 0

    yield _sse_event("run_start", {
        "type": "run_start",
        "run_id": run_id,
        "timestamp": _utc_now_iso(),
    })

    try:
        async with agent.run_stream_events(
            prompt,
            message_history=message_history if message_history else None,
            deps=settings,
        ) as event_stream:
            async for event in event_stream:
                if isinstance(event, PartStartEvent):
                    step_counter += 1

                elif isinstance(event, PartDeltaEvent) and isinstance(
                    event.delta, TextPartDelta
                ):
                    content_delta = event.delta.content_delta
                    if not content_delta:
                        continue
                    full_output += content_delta
                    yield _sse_event("text_delta", {
                        "type": "text_delta",
                        "run_id": run_id,
                        "delta": content_delta,
                    })

                elif isinstance(event, FunctionToolCallEvent):
                    call_id = event.part.tool_call_id
                    _tool_start_times[call_id] = time.monotonic()
                    args = event.part.args
                    if isinstance(args, str):
                        try:
                            args = json_mod.loads(args)
                        except json_mod.JSONDecodeError:
                            args = {"raw": args}
                    yield _sse_event("tool_call", {
                        "type": "tool_call",
                        "run_id": run_id,
                        "call_id": call_id,
                        "tool_name": event.part.tool_name,
                        "args": args if isinstance(args, dict) else {"raw": str(args)},
                        "timestamp": _utc_now_iso(),
                    })

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

                    yield _sse_event("tool_result", {
                        "type": "tool_result",
                        "run_id": run_id,
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "success": success,
                        "output": output,
                        "error_code": error_code,
                        "duration_ms": duration_ms,
                        "timestamp": _utc_now_iso(),
                    })

                elif isinstance(event, PartEndEvent):
                    pass

        canonical_slug = None
        display_name = None
        if settings.llm_model:
            slug = resolve_canonical_slug(settings.llm_provider, settings.llm_model)
            if slug:
                canonical_slug = slug
                c = get_canonical_by_slug(slug)
                if c:
                    display_name = c.display_name

        yield "data: [DONE]\n\n"
        yield _sse_event("metadata", {
            "type": "metadata",
            "run_id": run_id,
            "full_output": full_output,
            "canonical_slug": canonical_slug,
            "display_name": display_name,
            "provider_specific_id": settings.llm_model,
        })

    except Exception as e:
        yield _sse_event("error", {
            "type": "error",
            "run_id": run_id,
            "message": str(e),
            "error_id": uuid.uuid4().hex[:12],
        })
    finally:
        _tool_start_times.clear()
