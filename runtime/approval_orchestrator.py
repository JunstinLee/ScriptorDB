from __future__ import annotations

"""Backwards-compatible shim：审批编排已迁移至 approval_part/ 包。

实现见 approval_part/orchestrator.py、resumable.py、policy.py、pause.py、
controller.py、store.py。旧导入路径（含测试）经此转发。
"""

from approval_part.controller import TakeoverController, _BrowserTakeoverController
from approval_part.orchestrator import ApprovalOrchestrator, _LoopAction, _RunState
from approval_part.pause import ApprovalPauseState
from approval_part.policy import _classify_deferred_calls, _process_deferred_requests
from approval_part.resumable import _auto_approve_all, run_agent_stream_resumable

__all__ = [
    "ApprovalOrchestrator",
    "ApprovalPauseState",
    "TakeoverController",
    "run_agent_stream_resumable",
    "_process_deferred_requests",
    "_classify_deferred_calls",
    "_auto_approve_all",
    "_RunState",
    "_LoopAction",
    "_BrowserTakeoverController",
]
