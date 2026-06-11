from __future__ import annotations

from collections.abc import AsyncIterator

from agents.db_agent import get_agent
from config.models import fuzzy_match_model
from config.settings import Settings
from pydantic_ai.messages import ModelMessage


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
        async with agent.run_stream(
            prompt,
            message_history=message_history if message_history else None,
            deps=settings,
        ) as streamed:
            async for chunk in streamed.stream_text(delta=True):
                full_output += chunk
                yield _sse_lines(chunk) + "\n\n"

        yield f"data: [DONE]\n\n"
        yield f"event: metadata\ndata: {_sse_encode_json({'full_output': full_output})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {_sse_lines(str(e))}\n\n"


def _sse_lines(data: str) -> str:
    lines = data.split("\n")
    return "\n".join(f"data: {line}" if line else "data:" for line in lines)


def _sse_encode_json(obj: dict) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
