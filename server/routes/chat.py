from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

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
            yield sse_event

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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
