from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai.messages import ModelMessage

from config.app_config import AppConfig
from config.canonical_models import get_canonical_by_slug
from config.models import resolve_canonical_slug

from server.agent_runner import run_agent_stream
from server.run_tracker import RunTracker
from server.sse_format import sse_done, sse_event


_sse_event = sse_event  # 旧名称向后兼容


async def stream_agent_response(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    run_collector: dict[str, Any] | None = None,
    new_messages_collector: list[ModelMessage] | None = None,
) -> AsyncIterator[str]:
    """薄协调层：把 agent_runner 产出 dict 事件转为 SSE 字符串。

    接受外层传入的 run_collector 字典，结束时填充它（向后兼容）。
    """
    tracker = RunTracker()
    if run_collector is not None:
        run_collector.update(tracker.to_run_collector())

    async for event in run_agent_stream(
        prompt,
        message_history,
        config,
        model=model,
        provider=provider,
        tracker=tracker,
    ):
        ev_type = event.get("type", "")
        if ev_type == "new_messages":
            if new_messages_collector is not None:
                new_messages_collector.extend(event.get("messages", []))
            continue
        if ev_type == "metadata":
            slug = None
            display_name = None
            if config.llm_model:
                resolved = resolve_canonical_slug(config.llm_provider, config.llm_model)
                if resolved:
                    slug = resolved
                    c = get_canonical_by_slug(slug)
                    if c:
                        display_name = c.display_name
            event_payload = {
                **event,
                "canonical_slug": slug,
                "display_name": display_name,
                "provider_specific_id": config.llm_model,
            }
            yield sse_event("metadata", event_payload)
        else:
            yield sse_event(ev_type, event)

        if ev_type == "run_end":
            yield sse_done()

    if run_collector is not None:
        run_collector.update(tracker.to_run_collector())
