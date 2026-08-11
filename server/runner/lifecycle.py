from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelMessage

from agents.db_agent import get_agent
from config.app_config import AppConfig
from config.models import fuzzy_match_model
from logging_setup import get_logger
from server.run_tracker import RunTracker
from server.runner.errors import (
    CONNECTION_RETRY_EXCEPTIONS,
    MAX_CONNECTION_RETRIES,
    find_rate_limit,
)
from server.runner.events import run_start_event
from server.runner.finalize import (
    deferred_requests_event,
    error_event,
    metadata_event,
    new_messages_event,
    run_end_event,
    strip_leading_user_prompt,
)
from server.runner.translator import EventTranslator

logger = get_logger("agent_runner.lifecycle")


async def run_agent_stream(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Any | None = None,
    tracker: RunTracker | None = None,
    deferred_results: DeferredToolResults | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
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
        matched = fuzzy_match_model(config.llm_provider, model, config.workspace_id)
        if matched:
            config.llm_model = matched

    agent = agent or get_agent(config, model, provider)
    queue: asyncio.Queue[dict] = asyncio.Queue()
    local_tracker = tracker or RunTracker()
    checkpoint_id = uuid.uuid4().hex[:12]

    translator = EventTranslator(
        queue=queue,
        tracker=local_tracker,
        config=config,
        checkpoint_id=checkpoint_id,
        prompt=prompt,
        message_history=message_history,
    )

    yield run_start_event(local_tracker.run_id)

    async def run_agent() -> Any:
        config.run_id = local_tracker.run_id
        kwargs: dict[str, Any] = {
            "message_history": message_history if message_history else None,
            "deps": config,
            "event_stream_handler": translator.handle,
        }
        if deferred_results is not None:
            kwargs["deferred_tool_results"] = deferred_results
        attempts = 0
        while True:
            try:
                return await agent.run(prompt, **kwargs)
            except CONNECTION_RETRY_EXCEPTIONS as e:
                attempts += 1
                if attempts > MAX_CONNECTION_RETRIES:
                    raise
                logger.warning(
                    "agent run connection error (attempt %d/%d): %s",
                    attempts, MAX_CONNECTION_RETRIES, e,
                )
                await asyncio.sleep(1.0 * attempts)

    run_task = asyncio.create_task(run_agent())
    pending_get_task: asyncio.Task | None = None

    try:
        while True:
            if run_task.done() and queue.empty():
                break

            if queue.empty():
                get_task = asyncio.create_task(queue.get())
                pending_get_task = get_task
                try:
                    done, _pending = await asyncio.wait(
                        {get_task, run_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if get_task not in done:
                        get_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await get_task
                        continue
                    ev = get_task.result()
                finally:
                    pending_get_task = None
            else:
                ev = queue.get_nowait()

            yield ev

        result = await run_task

        if isinstance(result.output, DeferredToolRequests):
            deferred_new_messages = strip_leading_user_prompt(result.new_messages())
            if deferred_new_messages:
                yield new_messages_event(local_tracker.run_id, deferred_new_messages)
            yield deferred_requests_event(
                local_tracker.run_id, result.output, result.all_messages()
            )
            local_tracker.final_output = translator.full_output
            return

        if not translator.full_output and result.output:
            translator.full_output = str(result.output)
            local_tracker.final_output = translator.full_output

        new_messages = strip_leading_user_prompt(result.new_messages())
        yield new_messages_event(local_tracker.run_id, new_messages)

        local_tracker.finish()
        yield metadata_event(local_tracker.run_id, translator.full_output)
        yield run_end_event(local_tracker.run_id)
    except Exception as e:
        error_id = uuid.uuid4().hex[:12]
        local_tracker.fail(str(e))
        yield error_event(local_tracker.run_id, error_id, find_rate_limit(e))
        yield run_end_event(local_tracker.run_id)
    finally:
        if pending_get_task is not None and not pending_get_task.done():
            pending_get_task.cancel()
            with suppress(asyncio.CancelledError):
                await pending_get_task
        if run_task.done():
            with suppress(asyncio.CancelledError, Exception):
                run_task.result()
        else:
            run_task.cancel()
            with suppress(asyncio.CancelledError):
                await run_task
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
