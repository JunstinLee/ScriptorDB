from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.dependencies import require_workspace
from core.logging_setup import get_logger
from schemas import ApprovalSubmitRequest

from runtime.approval.run_registry import get_run_registry

logger = get_logger("routes.approve")

router = APIRouter(prefix="/api/sessions", tags=["approve"])


@router.post("/{session_id}/approve")
async def approve(session_id: str, req: ApprovalSubmitRequest):
    require_workspace()

    slot = get_run_registry().get(session_id)
    if slot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No active run for this session. The run may have finished, or its "
                "event stream dropped. Send a new message to start a new run."
            ),
        )
    orchestrator = slot.orchestrator

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
