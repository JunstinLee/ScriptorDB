from __future__ import annotations

import asyncio
import json as json_mod
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import suppress
from typing import Any

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.exceptions import FallbackExceptionGroup, ModelHTTPError
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
from logging_setup import get_logger
from server.approval_policy import (
    PendingTakeover,
    get_takeover_checkpoint_store,
)
from tools.tool_result import ToolResult

from server.run_tracker import RunTracker, utc_now_iso

logger = get_logger("agent_runner")


def _find_rate_limit(exc: BaseException) -> tuple[int, str] | None:
    """Walk the exception chain (and exception groups) looking for HTTP 429.

    Returns (status_code, model_name) when the failure is a model rate limit,
    None otherwise. pydantic-ai may surface ModelHTTPError directly, wrapped in
    UnexpectedModelBehavior, or inside a FallbackExceptionGroup, so the chain is
    traversed defensively.
    """
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ModelHTTPError) and current.status_code == 429:
            return (current.status_code, current.model_name)
        if isinstance(current, FallbackExceptionGroup):
            pending.extend(current.exceptions)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return None


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
    full_output = ""
    run_id = tracker.run_id if tracker else ""
    trace_step = 0
    handler_calls = 0
    queue: asyncio.Queue[dict] = asyncio.Queue()
    local_tracker = tracker or RunTracker()
    checkpoint_id = uuid.uuid4().hex[:12]
    tool_parts: list[Any] = []

    yield {
        "type": "run_start",
        "run_id": local_tracker.run_id,
        "timestamp": utc_now_iso(),
    }

    async def event_stream_handler(ctx: RunContext[AppConfig], events: Any) -> None:
        nonlocal full_output, trace_step, handler_calls
        handler_calls += 1
        handler_call = handler_calls
        try:
            async for event in events:
                if isinstance(event, FunctionToolCallEvent):
                    tool_parts.append(event.part)
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
                    tool_parts.append(event.part)
                    call_id = event.part.tool_call_id if event.part else "unknown"
                    tool_name = event.part.tool_name if event.part else "unknown"
                    duration_ms = local_tracker.tool_duration_ms(call_id)

                    success = True
                    output: Any = None
                    error_code: str | None = None
                    data: dict[str, Any] | None = None
                    content = event.part.content if event.part else None
                    if isinstance(content, ToolResult):
                        success = content.success
                        output = content.output
                        data = content.data
                        if content.error:
                            error_code = content.error.category
                            output = content.error.message
                    elif isinstance(content, str):
                        output = content
                    elif isinstance(content, dict):
                        output = json_mod.dumps(content, ensure_ascii=False)

                    logger.info(
                        "tool_result_event run_id=%s call_id=%s tool=%s content_type=%s "
                        "success=%s output_type=%s data_type=%s",
                        local_tracker.run_id, call_id, tool_name,
                        type(content).__name__ if content is not None else "None",
                        success,
                        type(output).__name__ if output is not None else "None",
                        type(data).__name__ if data is not None else "None",
                    )
                    local_tracker.complete_tool(
                        call_id, success, output, error_code, duration_ms, data=data
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
                        "data": data,
                        "timestamp": utc_now_iso(),
                    })

                    if tool_name and tool_name.startswith("browser_"):
                        try:
                            from browser import get_manager
                            mgr = get_manager()
                            state = await mgr.get_state()
                            actions = state.get("actions", [])
                            if actions:
                                latest = actions[-1]
                                await queue.put({
                                    "type": "browser_action",
                                    "run_id": local_tracker.run_id,
                                    "tool": latest.get("tool", tool_name),
                                    "selector": latest.get("selector", ""),
                                    "coords": latest.get("coords", {}),
                                    "success": latest.get("success", success),
                                    "detail": latest.get("detail", ""),
                                    "timestamp": latest.get("timestamp", utc_now_iso()),
                                })
                            takeover = mgr.takeover if mgr else None
                            if takeover and takeover.should_pause_agent():
                                takeover.enter_waiting()
                                logger.warning(f"agent paused for takeover reason={takeover.reason} trigger={takeover.trigger}")
                                _checkpoint = PendingTakeover(
                                    session_id=getattr(config, "chat_session_id", "") or "",
                                    run_id=local_tracker.run_id,
                                    checkpoint_id=checkpoint_id,
                                    prompt=prompt,
                                    message_history=list(message_history),
                                    turn_new_messages=(
                                        [ModelRequest(parts=list(tool_parts))]
                                        if tool_parts
                                        else []
                                    ),
                                    tool_invocations=list(local_tracker.tool_invocations),
                                    final_output=full_output,
                                    reason=takeover.reason,
                                    trigger=takeover.trigger,
                                    created_at=utc_now_iso(),
                                )
                                get_takeover_checkpoint_store().add(_checkpoint)
                                _state = await mgr.get_state()
                                await queue.put({
                                    "type": "human_takeover_request",
                                    "run_id": local_tracker.run_id,
                                    "checkpoint_id": checkpoint_id,
                                    "reason": takeover.reason,
                                    "trigger": takeover.trigger,
                                    "current_url": _state.get("url", ""),
                                    "screenshot_available": _state.get("screenshot_available", False),
                                    "timestamp": utc_now_iso(),
                                })
                        except Exception:
                            pass

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
            pass

    if agent is None:
        agent = get_agent(config, model, provider)

    async def run_agent() -> Any:
        config.run_id = local_tracker.run_id
        kwargs: dict[str, Any] = {
            "message_history": message_history if message_history else None,
            "deps": config,
            "event_stream_handler": event_stream_handler,
        }
        if deferred_results is not None:
            kwargs["deferred_tool_results"] = deferred_results
        return await agent.run(prompt, **kwargs)

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
            deferred_new_messages = result.new_messages()
            if (
                deferred_new_messages
                and isinstance(deferred_new_messages[0], ModelRequest)
                and all(
                    isinstance(p, UserPromptPart)
                    for p in deferred_new_messages[0].parts
                )
            ):
                deferred_new_messages = deferred_new_messages[1:]
            if deferred_new_messages:
                yield {
                    "type": "new_messages",
                    "run_id": local_tracker.run_id,
                    "messages": deferred_new_messages,
                }
            yield {
                "type": "_deferred_tool_requests",
                "run_id": local_tracker.run_id,
                "deferred": result.output,
                "all_messages": result.all_messages(),
            }
            local_tracker.final_output = full_output
            return

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
        local_tracker.fail(str(e))
        error_event: dict[str, Any] = {
            "type": "error",
            "run_id": local_tracker.run_id,
            "message": f"运行失败（ID: {error_id}），请联系管理员",
            "error_id": error_id,
        }
        rate_limit = _find_rate_limit(e)
        if rate_limit is not None:
            status_code, model_name = rate_limit
            error_event["error_type"] = "rate_limit"
            error_event["status_code"] = status_code
            error_event["model_name"] = model_name
            error_event["message"] = (
                "模型限流（HTTP 429 Too Many Requests），请求过于频繁，"
                "请稍等片刻后重试。"
            )
        yield error_event
        yield {
            "type": "run_end",
            "run_id": local_tracker.run_id,
            "timestamp": utc_now_iso(),
        }
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
