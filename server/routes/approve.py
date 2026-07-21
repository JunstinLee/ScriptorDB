from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from logging_setup import get_logger
from server.dependencies import get_config, require_workspace
from server.schemas import ApprovalSubmitRequest
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event
from services.chat_service import persist_chat_run

from server.routes.chat import get_orchestrator

logger = get_logger("routes.approve")

router = APIRouter(prefix="/api/sessions", tags=["approve"])


@router.post("/{session_id}/approve")
async def approve(session_id: str, req: ApprovalSubmitRequest):
    require_workspace()
    config = get_config()

    orchestrator = get_orchestrator(session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No pending approval for this session")

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    async def event_callback(event: dict[str, Any]) -> None:
        await event_queue.put(event)

    run_task = asyncio.create_task(
        orchestrator.resume_with_approval(
            req.request_id,
            req.approved_map,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        )
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
            completed = await run_task
            if completed:
                persist_chat_run(
                    session_id=session_id,
                    new_messages_collector=new_messages_collector,
                    run_collector=run_collector,
                )
                from server.routes.chat import remove_orchestrator
                remove_orchestrator(session_id)
