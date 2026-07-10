from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from logging_setup import get_logger
from server.approval_orchestrator import ApprovalOrchestrator, submit_approval
from server.dependencies import get_config, require_workspace
from server.schemas import (
    ApprovalSubmitRequest,
    ChatRequest,
    StoredRun,
    StoredToolInvocation,
)
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event

router = APIRouter(prefix="/api/sessions", tags=["chat"])
_log = get_logger("server.routes.chat")


@router.post("/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    require_workspace()
    config = get_config()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt)

    config.chat_session_id = session_id
    config.chat_prompt = req.prompt

    augmented_prompt = req.prompt
    if req.attachments:
        files_block = "\n".join(f"- {path}" for path in req.attachments)
        augmented_prompt = (
            f"The user has attached the following files:\n{files_block}\n\n"
            f"User request: {req.prompt}"
        )

    _log.info(
        "chat request: session_id=%s model=%s provider=%s attachments=%d prompt_len=%d augmented_len=%d",
        session_id,
        req.model,
        req.provider,
        len(req.attachments or []),
        len(req.prompt),
        len(augmented_prompt),
    )
    for path in req.attachments or []:
        _log.info("chat attachment: session_id=%s path=%s", session_id, path)

    model_messages = session.get_model_messages()

    async def generate():
        async for sse_event_str in _run_chat_turn(
            session_id=session_id,
            config=config,
            prompt=augmented_prompt,
            message_history=model_messages,
            model=req.model,
            provider=req.provider,
        ):
            yield sse_event_str

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_chat_turn(
    session_id: str,
    config: Any,
    prompt: str,
    message_history: list[ModelMessage],
    model: str | None = None,
    provider: str | None = None,
) -> AsyncIterator[str]:
    """Run one chat turn, including any deferred approval pause/resume."""
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    orchestrator = ApprovalOrchestrator(
        session_id=session_id,
        config=config,
        model=model,
        provider=provider,
    )

    async def event_callback(event: dict[str, Any]) -> None:
        await queue.put(event)

    run_task = asyncio.create_task(
        orchestrator.start_run(
            prompt,
            message_history,
            event_callback=event_callback,
        )
    )

    try:
        pending_request_id: str | None = None
        while True:
            if run_task.done() and queue.empty():
                break

            event = await queue.get()
            ev_type = event.get("type")

            if ev_type == "approval_request":
                pending_request_id = event.get("request_id")
                yield _dict_to_sse(event)
                break

            yield _dict_to_sse(event)

        summary = await run_task
        run_collector.update(summary)
        new_messages_collector.extend(summary.get("new_messages", []))

    except Exception as e:
        _log.exception("chat turn error: session_id=%s", session_id)
        yield sse_event("error", {"type": "error", "message": str(e)})
        yield sse_event("run_end", {"type": "run_end", "run_id": "", "timestamp": ""})
        return

    if new_messages_collector:
        session.add_model_messages(new_messages_collector)

    if run_collector.get("status") == "completed" and run_collector.get("final_output"):
        session.add_assistant_message(run_collector["final_output"])

    if run_collector:
        run = StoredRun(
            run_id=run_collector["run_id"],
            status=run_collector["status"],
            tool_invocations=[
                StoredToolInvocation(**inv)
                for inv in run_collector.get("tool_invocations", [])
            ],
            final_output=run_collector.get("final_output", ""),
            started_at=run_collector["started_at"],
            ended_at=run_collector.get("ended_at"),
            error_message=run_collector.get("error_message"),
        )
        session.add_run(run)
        get_session_store().save()
        _log.info(
            "chat run persisted: session_id=%s run_id=%s status=%s tools=%d",
            session_id,
            run.run_id,
            run.status,
            len(run.tool_invocations),
        )


@router.post("/{session_id}/approve")
async def approve(session_id: str, req: ApprovalSubmitRequest):
    require_workspace()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    config = get_config()
    pending = await submit_approval(req.request_id, req.approved_map)
    if pending is None:
        raise HTTPException(status_code=404, detail="Approval request not found or already resolved")

    async def generate():
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        run_collector: dict[str, Any] = {}
        new_messages_collector: list[ModelMessage] = []

        orchestrator = ApprovalOrchestrator(
            session_id=session_id,
            config=config,
        )

        async def event_callback(event: dict[str, Any]) -> None:
            await queue.put(event)

        run_task = asyncio.create_task(
            orchestrator.resume_with_approval(
                req.request_id,
                pending.approved_map,
                event_callback=event_callback,
                run_collector=run_collector,
                new_messages_collector=new_messages_collector,
            )
        )

        try:
            while True:
                if run_task.done() and queue.empty():
                    break
                event = await queue.get()
                yield _dict_to_sse(event)

            completed = await run_task

            if new_messages_collector:
                session.add_model_messages(new_messages_collector)

            if run_collector.get("status") == "completed" and run_collector.get("final_output"):
                session.add_assistant_message(run_collector["final_output"])

            if run_collector:
                run = StoredRun(
                    run_id=run_collector["run_id"],
                    status=run_collector["status"],
                    tool_invocations=[
                        StoredToolInvocation(**inv)
                        for inv in run_collector.get("tool_invocations", [])
                    ],
                    final_output=run_collector.get("final_output", ""),
                    started_at=run_collector["started_at"],
                    ended_at=run_collector.get("ended_at"),
                    error_message=run_collector.get("error_message"),
                )
                session.add_run(run)
                get_session_store().save()
                _log.info(
                    "approve run persisted: session_id=%s run_id=%s status=%s tools=%d",
                    session_id,
                    run.run_id,
                    run.status,
                    len(run.tool_invocations),
                )

            if completed:
                yield sse_done()
        except Exception as e:
            _log.exception("approve turn error: session_id=%s", session_id)
            yield sse_event("error", {"type": "error", "message": str(e)})
            yield sse_event("run_end", {"type": "run_end", "run_id": "", "timestamp": ""})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _dict_to_sse(event: dict[str, Any]) -> str:
    ev_type = event.get("type", "")
    if ev_type == "new_messages":
        return ""
    if ev_type == "metadata":
        from config.canonical_models import get_canonical_by_slug
        from config.models import resolve_canonical_slug

        config = get_config()
        slug = None
        display_name = None
        if config.llm_model:
            resolved = resolve_canonical_slug(config.llm_provider, config.llm_model)
            if resolved:
                slug = resolved
                c = get_canonical_by_slug(slug)
                if c:
                    display_name = c.display_name
        return sse_event(
            "metadata",
            {
                **event,
                "canonical_slug": slug,
                "display_name": display_name,
                "provider_specific_id": config.llm_model,
            },
        )
    if ev_type == "run_end":
        return sse_event(ev_type, event) + sse_done()
    return sse_event(ev_type, event)
