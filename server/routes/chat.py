from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from server.approval_orchestrator import ApprovalOrchestrator, submit_approval
from server.dependencies import get_config, require_workspace
from server.schemas import (
    ApprovalSubmitRequest,
    ChatRequest,
)
from server.services.chat_service import persist_chat_run
from server.services.sse_presenter import event_to_sse
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event

router = APIRouter(prefix="/api/sessions", tags=["chat"])


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
                yield event_to_sse(event, config.llm_provider, config.llm_model)
                break

            yield event_to_sse(event, config.llm_provider, config.llm_model)

        summary = await run_task
        run_collector.update(summary)
        new_messages_collector.extend(summary.get("new_messages", []))

    except Exception as e:
        yield sse_event("error", {"type": "error", "message": str(e)})
        yield sse_event("run_end", {"type": "run_end", "run_id": "", "timestamp": ""})
        return

    if new_messages_collector:
        session.add_model_messages(new_messages_collector)

    if run_collector.get("status") == "completed" and run_collector.get("final_output"):
        session.add_assistant_message(run_collector["final_output"])

    persist_chat_run(session_id, new_messages_collector, run_collector)


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
                yield event_to_sse(event, config.llm_provider, config.llm_model)

            completed = await run_task

            if new_messages_collector:
                session.add_model_messages(new_messages_collector)

            if run_collector.get("status") == "completed" and run_collector.get("final_output"):
                session.add_assistant_message(run_collector["final_output"])

            persist_chat_run(session_id, new_messages_collector, run_collector)

            if completed:
                yield sse_done()
        except Exception as e:
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
