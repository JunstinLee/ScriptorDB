from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from server.dependencies import get_config, require_workspace
from server.schemas import ChatRequest, StoredRun, StoredToolInvocation
from server.sessions import get_session_store
from server.streaming import stream_agent_response

router = APIRouter(prefix="/api/sessions", tags=["chat"])


@router.post("/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    require_workspace()
    config = get_config()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt)

    model_messages = session.get_model_messages()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    async def generate():
        async for sse_event in stream_agent_response(
            req.prompt,
            model_messages,
            config,
            model=req.model,
            provider=req.provider,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
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
