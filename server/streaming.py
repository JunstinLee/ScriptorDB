from __future__ import annotations

import json as json_mod
from collections.abc import AsyncIterator

from agents.db_agent import get_agent
from config.canonical_models import get_canonical_by_slug
from config.models import fuzzy_match_model, resolve_canonical_slug
from config.settings import Settings
from pydantic_ai.messages import ModelMessage, PartDeltaEvent, TextPartDelta
from tools.tool_result import ToolResult


def _sse_lines(data: str) -> str:
    lines = data.split("\n")
    return "\n".join(f"data: {line}" if line else "data:" for line in lines)


def _sse_encode_json(obj: dict) -> str:
    return json_mod.dumps(obj, ensure_ascii=False)


def _serialize_tool_result(result: ToolResult) -> str:
    return result.model_dump_json(ensure_ascii=False)


async def stream_agent_response(
    prompt: str,
    message_history: list[ModelMessage],
    settings: Settings,
    model: str | None = None,
    provider: str | None = None,
) -> AsyncIterator[str]:
    if provider:
        settings.llm_provider = provider
    if model:
        matched = fuzzy_match_model(settings.llm_provider, model)
        if matched:
            settings.llm_model = matched

    agent = get_agent(model, provider)
    full_output = ""

    try:
        async with agent.run_stream_events(
            prompt,
            message_history=message_history if message_history else None,
            deps=settings,
        ) as event_stream:
            async for event in event_stream:
                if isinstance(event, PartDeltaEvent) and isinstance(
                    event.delta, TextPartDelta
                ):
                    content_delta = event.delta.content_delta
                    if not content_delta:
                        continue
                    full_output += content_delta
                    yield _sse_lines(content_delta) + "\n\n"

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
        yield (
            "event: metadata\n"
            f"data: {_sse_encode_json({'full_output': full_output, 'canonical_slug': canonical_slug, 'display_name': display_name, 'provider_specific_id': settings.llm_model})}\n\n"
        )

    except Exception as e:
        error_id = None
        yield f"event: error\ndata: {_sse_encode_json({'message': str(e), 'error_id': error_id})}\n\n"
