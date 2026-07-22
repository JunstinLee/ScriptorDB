from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LOW_RISK_WRITE_TOOLS = frozenset({
    "write_csv",
    "write_file",
    "export_excel",
    "create_table",
    "execute_ddl",
    "write_data",
    "run_python_code",
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
