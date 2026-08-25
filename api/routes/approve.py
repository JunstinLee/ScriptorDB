from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.dependencies import require_workspace
from core.logging_setup import get_logger
from schemas import ApprovalSubmitRequest

from api.routes.chat import get_orchestrator

logger = get_logger("routes.approve")

router = APIRouter(prefix="/api/sessions", tags=["approve"])


@router.post("/{session_id}/approve")
async def approve(session_id: str, req: ApprovalSubmitRequest):
    require_workspace()

    orchestrator = get_orchestrator(session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No pending approval for this session")

    # 不重启 run、不开新 SSE 流：仅构建审批结果并唤醒挂起的 run
    # （与 /takeover/complete 同模式）；后续事件继续由原 chat SSE 流推送。
    result = orchestrator.signal_approval(
        req.request_id,
        req.approved_map,
        override_args=req.override_args,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "Cannot resume approval"))
    return result
