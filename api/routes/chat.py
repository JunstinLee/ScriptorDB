from __future__ import annotations

"""chat 路由：只做「启动 run + 订阅事件总线」。

run 的生存期由 `runtime/approval/run_owner.execute_run` 持有——订阅者（`/chat`
或 `GET /sessions/{id}/stream`）断开不影响 run；恢复端点唤醒原 run，事件经
`RunEventBus` 按 `from_index` 游标重放。
"""

import asyncio
from collections.abc import AsyncIterator
from copy import copy

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.logging_setup import get_logger
from runtime.approval.event_bus import RunEventBus
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.run_owner import execute_run
from runtime.approval.run_registry import ActiveRun, get_run_registry
from api.dependencies import get_app_context, get_config, require_workspace
from schemas import ChatRequest
from runtime.sessions import get_session_store
from api.sse_format import sse_done, sse_event
from services.chat_service import repair_tool_message_pairs
from services.prompt_service import CrawlError, augment_prompt

logger = get_logger("routes.chat")

router = APIRouter(prefix="/api/sessions", tags=["chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# 挂起事件：推给订阅者后流保持打开，等待恢复端点唤醒同一 run
_SUSPEND_EVENTS = frozenset({"approval_request", "human_takeover_request"})


async def _stream_bus(
    bus: RunEventBus, from_index: int, session_id: str
) -> AsyncIterator[str]:
    """把总线事件编码为 SSE 帧，直到 run 终态（run_end）或总线关闭。"""
    try:
        async for index, event in bus.subscribe(from_index):
            ev_type = event.get("type", "")
            if ev_type in _SUSPEND_EVENTS:
                # 与接管一致：流保持打开，等待审批决定后继续推送同一 run 的事件
                yield sse_event(ev_type, event, index)
                continue
            if ev_type == "run_end":
                yield sse_event(ev_type, event, index)
                yield sse_done()
                return
            # metadata / error / text_delta / tool_call / tool_result / trace /
            # takeover_state_change / takeover_cancelled / stream_truncated：原样转发
            yield sse_event(ev_type, event, index)
    except asyncio.CancelledError:
        # 订阅者断开：不 cancel run、不动 registry、不做落盘——run 由 owner 持有
        logger.info(
            "chat_stream_detached session_id=%s last_index=%s",
            session_id, bus.last_index,
        )
        raise


def _streaming_response(
    bus: RunEventBus, from_index: int, session_id: str
) -> StreamingResponse:
    return StreamingResponse(
        _stream_bus(bus, from_index, session_id),
        media_type="text/event-stream",
        headers=dict(_SSE_HEADERS),
    )


@router.post("/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    require_workspace()
    config = get_config()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt, attachments=req.attachments, crawl_url=req.crawl_url)

    # per-run 配置副本：会话级字段不再写入全局 settings 单例，
    # 避免并发会话互相覆盖（undo 钩子/translator 经 deps 读取）。
    run_config = copy(config)
    run_config.chat_session_id = session_id
    run_config.chat_prompt = req.prompt
    run_config.run_id = ""

    try:
        augmented_prompt = await augment_prompt(
            req.prompt, attachments=req.attachments, crawl_url=req.crawl_url
        )
    except CrawlError as e:
        raise HTTPException(status_code=502, detail=f"Crawl failed: {e}")

    model_messages = repair_tool_message_pairs(session.get_model_messages())

    # 409 检查、槽位构造、注册、建 task 必须在同一段无 await 的同步代码里：
    # 否则两个并发 POST /chat 都能通过检查，同一 session 起两个 run。
    registry = get_run_registry()
    if registry.get(session_id) is not None:
        raise HTTPException(
            status_code=409,
            detail="A run is already active for this session; attach to its stream instead",
        )

    bus = RunEventBus()
    orchestrator = ApprovalOrchestrator(
        session_id,
        run_config,
        model=req.model,
        provider=req.provider,
        app_context=get_app_context(),
        suspend_callback=lambda kind, reason: registry.mark_suspended(
            session_id, kind or "", reason
        ),
    )
    slot = ActiveRun(session_id=session_id, orchestrator=orchestrator, bus=bus)
    registry.register(slot)
    # 任务由 chat() 创建并回填槽位（owner 协程不建 task）；槽位持有强引用，
    # 否则 asyncio 的弱引用语义会让 owner task 在执行中被回收。
    slot.task = asyncio.create_task(
        execute_run(slot=slot, prompt=augmented_prompt, message_history=model_messages)
    )

    return _streaming_response(bus, 0, session_id)


@router.get("/{session_id}/stream")
async def attach_stream(session_id: str, from_index: int = 0):
    """重挂订阅：按 from_index 游标重放活动 run 的历史事件。"""
    require_workspace()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    slot = get_run_registry().get(session_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="No active run for this session")
    return _streaming_response(slot.bus, from_index, session_id)


@router.get("/{session_id}/active-run")
async def active_run(session_id: str):
    """当前活动 run 的状态：run_id / 挂起类型 / 最新游标。"""
    require_workspace()
    slot = get_run_registry().get(session_id)
    if slot is None:
        return {"run_id": "", "suspended": None, "reason": "", "last_index": 0}
    return {
        "run_id": slot.run_id,
        "suspended": slot.suspended,
        "reason": slot.suspend_reason,
        "last_index": slot.bus.last_index,
    }
