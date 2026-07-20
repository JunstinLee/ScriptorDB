from __future__ import annotations

import traceback
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from logging_setup import get_logger
from server.dependencies import get_config, require_workspace
from server.schemas import ChatRequest
from services.chat_service import persist_chat_run
from server.sessions import get_session_store
from server.streaming import stream_agent_response
from services.prompt_service import CrawlError, augment_prompt

logger = get_logger("routes.chat")

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

    try:
        augmented_prompt = await augment_prompt(
            req.prompt, attachments=req.attachments, crawl_url=req.crawl_url
        )
    except CrawlError as e:
        raise HTTPException(status_code=502, detail=f"网页抓取失败: {e}")

    model_messages = session.get_model_messages()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    async def generate():
        async for sse_event_str in stream_agent_response(
            prompt=augmented_prompt,
            message_history=model_messages,
            config=config,
            model=req.model,
            provider=req.provider,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        ):
            yield sse_event_str

        persist_chat_run(
            session_id=session_id,
            new_messages_collector=new_messages_collector,
            run_collector=run_collector,
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
