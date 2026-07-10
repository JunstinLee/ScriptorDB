from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai.messages import ModelMessage

from config.app_config import AppConfig
from logging_setup import get_logger

from server.agent_runner import run_agent_stream
from server.run_tracker import RunTracker
from server.services.sse_presenter import event_to_sse


_log = get_logger("server.streaming")


async def stream_agent_response(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Any | None = None,
    run_collector: dict[str, Any] | None = None,
    new_messages_collector: list[ModelMessage] | None = None,
) -> AsyncIterator[str]:
    """薄协调层：把 agent_runner 产出 dict 事件转为 SSE 字符串。

    接受外层传入的 run_collector 字典，结束时填充它（向后兼容）。
    """
    tracker = RunTracker()
    if run_collector is not None:
        run_collector.update(tracker.to_run_collector())

    _log.info(
        "stream_agent_response: start run_id=%s provider=%s model=%s prompt_len=%d",
        tracker.run_id,
        config.llm_provider,
        config.llm_model,
        len(prompt),
    )

    async for event in run_agent_stream(
        prompt,
        message_history,
        config,
        model=model,
        provider=provider,
        agent=agent,
        tracker=tracker,
    ):
        ev_type = event.get("type", "")
        _log.debug(
            "stream event: run_id=%s type=%s", tracker.run_id, ev_type
        )
        if ev_type == "new_messages":
            if new_messages_collector is not None:
                new_messages_collector.extend(event.get("messages", []))
            continue

        yield event_to_sse(event, config.llm_provider, config.llm_model)

        if ev_type == "run_end":
            _log.info(
                "stream_agent_response: end run_id=%s status=%s",
                tracker.run_id,
                tracker.status,
            )

    if run_collector is not None:
        run_collector.update(tracker.to_run_collector())
