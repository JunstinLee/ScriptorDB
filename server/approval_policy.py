from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage

LOW_RISK_WRITE_TOOLS = frozenset({
    "write_csv",
    "write_file",
    "export_excel",
    "create_table",
    "execute_ddl",
    "write_data",
    "python_sandbox_execute",
})

HIGH_RISK_IMPORT_TOOLS = frozenset({
    "import_csv_to_db",
    "import_excel_to_db",
})

IMPORT_ROW_THRESHOLD = 100


@dataclass
class ApprovalPolicy:
    auto_approve_low_risk: bool = True
    row_threshold: int = IMPORT_ROW_THRESHOLD


@dataclass
class PendingApproval:
    request_id: str
    session_id: str
    run_id: str
    message_history: list[Any]
    deferred_calls: list[dict[str, Any]]
    approved_map: dict[str, bool] = field(default_factory=dict)
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)


class PendingApprovalStore:
    def __init__(self):
        self._pending: dict[str, PendingApproval] = {}

    def add(self, request_id: str, pending: PendingApproval) -> None:
        self._pending[request_id] = pending

    def pop(self, request_id: str) -> PendingApproval | None:
        return self._pending.pop(request_id, None)

    def get(self, request_id: str) -> PendingApproval | None:
        return self._pending.get(request_id)


_pending_store = PendingApprovalStore()


def get_pending_store() -> PendingApprovalStore:
    return _pending_store


@dataclass
class PendingTakeover:
    """接管暂停时的运行 checkpoint。

    保存暂停前 message history、当前回合新增模型消息（含工具调用/结果）、
    工具调用记录、已生成文本和触发原因，供恢复时重建完整上下文。
    """
    session_id: str
    run_id: str
    checkpoint_id: str
    prompt: str
    message_history: list[Any]
    turn_new_messages: list[Any]
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""
    reason: str = ""
    trigger: str = ""
    created_at: str = ""


class TakeoverCheckpointStore:
    """以 session_id 为索引的活动 takeover checkpoint store。

    同一 session 只能存在一个活动 checkpoint；读取/弹出时同时校验 run_id。
    """

    def __init__(self):
        self._by_session: dict[str, PendingTakeover] = {}

    def add(self, checkpoint: PendingTakeover) -> None:
        self._by_session[checkpoint.session_id] = checkpoint

    def get(self, session_id: str) -> PendingTakeover | None:
        return self._by_session.get(session_id)

    def get_for_run(self, session_id: str, run_id: str) -> PendingTakeover | None:
        checkpoint = self._by_session.get(session_id)
        if checkpoint is None:
            return None
        if run_id and checkpoint.run_id != run_id:
            return None
        return checkpoint

    def pop(self, session_id: str, run_id: str = "") -> PendingTakeover | None:
        checkpoint = self._by_session.get(session_id)
        if checkpoint is None:
            return None
        if run_id and checkpoint.run_id != run_id:
            return None
        return self._by_session.pop(session_id, None)

    def remove(self, session_id: str) -> PendingTakeover | None:
        return self._by_session.pop(session_id, None)


_takeover_checkpoint_store = TakeoverCheckpointStore()


def get_takeover_checkpoint_store() -> TakeoverCheckpointStore:
    return _takeover_checkpoint_store
