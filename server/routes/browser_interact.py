from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from server.dependencies import get_config, require_workspace
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event
from services.chat_service import persist_chat_run

from server.routes.chat import get_orchestrator, remove_orchestrator

router = APIRouter(prefix="/api/browser", tags=["browser_interact"])


@router.post("/takeover/complete")
async def complete_human_takeover(
    session_id: str,
    result: str,
):
    require_workspace()
    config = get_config()

    orchestrator = get_orchestrator(session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No active run for this session")

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []
    persisted = False

    async def event_callback(event: dict[str, Any]) -> None:
        await event_queue.put(event)

    run_task = asyncio.create_task(
        orchestrator.resume_after_takeover(
            result,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        )
    )

    async def generate():
        nonlocal run_collector, new_messages_collector, persisted

        try:
            while True:
                if run_task.done() and event_queue.empty():
                    completed = await run_task
                    if completed:
                        persist_chat_run(
                            session_id=session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(session_id)
                        persisted = True
                    break

                event = await event_queue.get()
                ev_type = event.get("type", "")

                if ev_type == "new_messages":
                    new_messages_collector.extend(event.get("messages", []))
                    continue

                if ev_type == "metadata":
                    continue

                if ev_type == "run_end":
                    completed = await run_task
                    if completed:
                        persist_chat_run(
                            session_id=session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(session_id)
                        persisted = True
                    yield sse_event(ev_type, event)
                    yield sse_done()
                    break

                if ev_type == "human_takeover_request":
                    yield sse_event(ev_type, event)
                    return

                yield sse_event(ev_type, event)
        finally:
            if not persisted and run_task.done():
                try:
                    if run_task.result() and run_collector.get("run_id"):
                        persist_chat_run(
                            session_id=session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(session_id)
                except Exception:
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
