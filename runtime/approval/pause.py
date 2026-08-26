from __future__ import annotations

"""审批暂停状态：复用接管暂停（RunPauseState）的挂起/唤醒语义。"""

from dataclasses import dataclass

from pydantic_ai import DeferredToolResults

from runtime.runner.takeover_hook import RunPauseState


@dataclass
class ApprovalPauseState(RunPauseState):
    """审批暂停：复用 RunPauseState 的挂起/唤醒语义，追加审批决策。"""

    decision: DeferredToolResults | None = None
