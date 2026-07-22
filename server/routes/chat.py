from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from logging_setup import get_logger
from server.approval_orchestrator import ApprovalOrchestrator
from server.dependencies import get_config, require_workspace
from server.schemas import ChatRequest
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event
from services.chat_service import persist_chat_run
from services.prompt_service import CrawlError, augment_prompt

logger = get_logger("routes.chat")

router = APIRouter(prefix="/api/sessions", tags=["chat"])

_active_orchestrators: dict[str, ApprovalOrchestrator] = {}


async def _stream_orchestrator_events(
    orchestrator: ApprovalOrchestrator,
    prompt: str,
    message_history: list[ModelMessage],
    session_id: str,
) -> StreamingResponse:
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    async def event_callback(event: dict[str, Any]) -> None:
        await event_queue.put(event)

    run_task = asyncio.create_task(
        orchestrator.start_run(prompt, message_history, event_callback)
    )

    async def generate():
        nonlocal run_collector, new_messages_collector

        try:
            while True:
                if run_task.done() and event_queue.empty():
                    break

                event = await event_queue.get()
                ev_type = event.get("type", "")

                if ev_type == "new_messages":
                    new_messages_collector.extend(event.get("messages", []))
                    continue

                if ev_type == "metadata":
                    continue

                yield sse_event(ev_type, event)

                if ev_type == "approval_request":
                    return
                if ev_type == "run_end":
                    yield sse_done()
                    break
        finally:
            summary = await run_task
            if summary["status"] == "completed":
                new_messages_collector.extend(summary.get("new_messages", []))
                persist_chat_run(
                    session_id=session_id,
                    new_messages_collector=new_messages_collector,
                    run_collector=summary,
                )
            elif summary["status"] == "running":
                # Paused for deferred-tool approval: checkpoint the user message
                # and this turn's model messages (incl. the deferred tool calls)
                # so a backend restart does not lose the turn.
                session = get_session_store().get(session_id)
                if session is not None:
                    if summary.get("new_messages"):
                        session.add_model_messages(summary["new_messages"])
                    if summary.get("final_output"):
                        session.add_assistant_message(summary["final_output"])
                    get_session_store().save()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    require_workspace()
    config = get_config()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt, attachments=req.attachments, crawl_url=req.crawl_url)

    config.chat_session_id = session_id
    config.chat_prompt = req.prompt

    try:
        augmented_prompt = await augment_prompt(
            req.prompt, attachments=req.attachments, crawl_url=req.crawl_url
        )
    except CrawlError as e:
        raise HTTPException(status_code=502, detail=f"网页抓取失败: {e}")

    model_messages = session.get_model_messages()

    orchestrator = ApprovalOrchestrator(
        session_id, config, model=req.model, provider=req.provider
    )
    _active_orchestrators[session_id] = orchestrator

    return await _stream_orchestrator_events(
        orchestrator, augmented_prompt, model_messages, session_id
    )


def get_orchestrator(session_id: str) -> ApprovalOrchestrator | None:
    return _active_orchestrators.get(session_id)


def remove_orchestrator(session_id: str) -> ApprovalOrchestrator | None:
    return _active_orchestrators.pop(session_id, None)
