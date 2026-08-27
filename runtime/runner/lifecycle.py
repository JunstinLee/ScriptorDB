from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import UsageLimits

from agents.db_agent import resolve_agent
from config.app_config import AppConfig
from core.logging_setup import get_logger
from runtime.run_tracker import RunTracker, utc_now_iso
from runtime.runner.errors import (
    CONNECTION_RETRY_EXCEPTIONS,
    MAX_CONNECTION_RETRIES,
    find_rate_limit,
)
from runtime.runner.events import run_start_event, takeover_cancelled_event
from runtime.runner.finalize import (
    deferred_requests_event,
    error_event,
    metadata_event,
    new_messages_event,
    run_end_event,
    strip_leading_user_prompt,
)
from runtime.runner.takeover_hook import RunPauseState, TakeoverCancelledError
from runtime.runner.translator import EventTranslator

logger = get_logger("agent_runner.lifecycle")


def _is_cancellation(exc: BaseException | None) -> bool:
    """沿异常链查找 TakeoverCancelledError。

    pydantic-ai 可能包装 event_stream_handler 抛出的异常；命中链上任意
    一环即视为用户取消（走取消终态而非 error 终态）。
    """
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, TakeoverCancelledError):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


async def run_agent_stream(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Any = None,
    tracker: RunTracker | None = None,
    deferred_results: DeferredToolResults | None = None,
    pause: RunPauseState | None = None,
    session_id: str = "",
) -> AsyncGenerator[dict[str, Any], None]:
    """纯编排层：启动 agent.run()，通过 asyncio.Queue 收集事件，产出标准化 dict 事件。

    不再产出 SSE 字符串，由 streaming 层负责包装。

    事件类型：
    - run_start, run_end, error, metadata
    - tool_call, tool_result
    - text_delta
    - trace
    - takeover_cancelled（接管取消时的终态）
    """
    agent = agent or resolve_agent(config, model, provider)
    queue: asyncio.Queue[dict] = asyncio.Queue()
    local_tracker = tracker or RunTracker()
    checkpoint_id = uuid.uuid4().hex[:12]

    translator = EventTranslator(
        queue=queue,
        tracker=local_tracker,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        prompt=prompt,
        message_history=message_history,
        pause=pause,
    )

    yield run_start_event(local_tracker.run_id)

    async def run_agent() -> Any:
        config.run_id = local_tracker.run_id
        kwargs: dict[str, Any] = {
            "message_history": message_history if message_history else None,
            "deps": config,
            "event_stream_handler": translator.handle,
            # pydantic-ai 默认 request_limit=50：浏览器任务每个工具调用消耗
            # 2 次模型请求，长流程 25 个工具调用即触顶导致 run 被强制中止。
            # usage_limits 是 run() 的运行时参数（非 Agent 构造参数），放宽到 200。
            "usage_limits": UsageLimits(request_limit=200),
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
            return

        if not local_tracker.final_output and result.output:
            local_tracker.final_output = str(result.output)

        new_messages = strip_leading_user_prompt(result.new_messages())
        yield new_messages_event(local_tracker.run_id, new_messages)

        local_tracker.finish()
        yield metadata_event(local_tracker.run_id, local_tracker.final_output)
        yield run_end_event(local_tracker.run_id)
    except Exception as e:
        if _is_cancellation(e):
            # 取消（含被 pydantic-ai 包装后）：统一转为取消终态
            local_tracker.status = "cancelled"
            local_tracker.ended_at = utc_now_iso()
            reason = "接管已取消"
            try:
                from browser import get_manager
                takeover = get_manager().takeover
                reason = takeover.reason or reason
            except Exception:
                pass
            yield takeover_cancelled_event(run_id=local_tracker.run_id, reason=reason)
        else:
            error_id = uuid.uuid4().hex[:12]
            local_tracker.fail(str(e))
            yield error_event(local_tracker.run_id, error_id, find_rate_limit(e), str(e))
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
