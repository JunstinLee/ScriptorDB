from __future__ import annotations

"""活动 run 注册表（模块级单例，风格对齐 store.py）。

取代 api/routes/chat.py 的 `_active_orchestrators`：run 的生存期由 owner 协程
（runtime/approval/run_owner.py）持有，注册表只按 session_id 索引当前活动槽位，
供 `/chat` 的 409 检查、`/stream` 重挂、恢复/审批端点查表使用。

`ApprovalOrchestrator` 不反向依赖本模块（`ActiveRun` 需要 orchestrator，
orchestrator 若需要 `ActiveRun` 则构造循环无法成立）；挂起标记由 chat() 经
`suspend_callback` 注入。
"""

import asyncio
from dataclasses import dataclass

from runtime.approval.event_bus import RunEventBus
from runtime.approval.orchestrator import ApprovalOrchestrator


@dataclass
class ActiveRun:
    """一次活动 run 的槽位：编排器 + 事件总线 + 承载 task。"""

    session_id: str
    orchestrator: ApprovalOrchestrator
    bus: RunEventBus
    task: asyncio.Task | None = None
    suspended: str | None = None  # "takeover" | "approval" | None
    suspend_reason: str = ""

    @property
    def run_id(self) -> str:
        """派生自 orchestrator：run_id 生成于 start_run 内部，槽位不再复制一份。"""
        return self.orchestrator.run_id


class RunRegistry:
    def __init__(self) -> None:
        self._slots: dict[str, ActiveRun] = {}

    def register(self, slot: ActiveRun) -> ActiveRun:
        """存入已构造好的槽位（不创建槽位、不接收 orchestrator 构造参数）。"""
        self._slots[slot.session_id] = slot
        return slot

    def get(self, session_id: str) -> ActiveRun | None:
        return self._slots.get(session_id)

    def get_by_run(self, session_id: str, run_id: str) -> ActiveRun | None:
        """按 session_id + run_id 查表；run_id 为空时退化为按 session 查。"""
        slot = self._slots.get(session_id)
        if slot is None:
            return None
        if run_id and slot.run_id != run_id:
            return None
        return slot

    def mark_suspended(self, session_id: str, kind: str, reason: str = "") -> None:
        """写挂起标记（"takeover"/"approval"）；kind 为空表示已恢复/终态。"""
        slot = self._slots.get(session_id)
        if slot is None:
            return
        slot.suspended = kind or None
        slot.suspend_reason = reason if kind else ""

    def remove(self, session_id: str, run_id: str = "") -> ActiveRun | None:
        """注销槽位；run_id 非空且不匹配时不注销（幂等）。"""
        slot = self._slots.get(session_id)
        if slot is None:
            return None
        if run_id and slot.run_id != run_id:
            return None
        return self._slots.pop(session_id, None)


_registry = RunRegistry()


def get_run_registry() -> RunRegistry:
    return _registry
