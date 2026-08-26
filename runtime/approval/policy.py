from __future__ import annotations

"""审批策略：工具分级、deferred 调用分流（纯函数）+ 分流落库与事件构造。

原位于 runtime/approval_orchestrator.py / approval_policy.py，随审批域
迁移至 runtime.approval/。策略判定（_classify_deferred_calls）与副作用
（落库、事件构造）分离，便于独立测试。
"""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelMessage

from runtime.import_inspector import count_import_rows
from runtime.approval.store import PendingApproval, get_pending_store

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

# 人工确认工具：deferred 调用一律挂起等待用户在确认抽屉中审批（可改值后应用）。
HUMAN_APPROVAL_TOOLS = frozenset({"browser_apply_filter"})

IMPORT_ROW_THRESHOLD = 100


@dataclass
class ApprovalPolicy:
    auto_approve_low_risk: bool = True
    row_threshold: int = IMPORT_ROW_THRESHOLD


def _classify_deferred_calls(
    deferred: DeferredToolRequests,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """纯函数：把 deferred 调用分为自动批准组与人工审批组（无副作用）。"""
    auto_calls: list[Any] = []
    pending_calls: list[dict[str, Any]] = []

    for call in deferred.approvals:
        tool_name = call.tool_name
        args = call.args_as_dict() if hasattr(call, "args_as_dict") else {}
        if tool_name in LOW_RISK_WRITE_TOOLS:
            auto_calls.append(call)
            continue
        if tool_name in HIGH_RISK_IMPORT_TOOLS:
            filepath = args.get("filepath", "") if isinstance(args, dict) else ""
            row_count = count_import_rows(filepath) if filepath else None
            if row_count is not None and row_count > IMPORT_ROW_THRESHOLD:
                pending_calls.append({
                    "tool_call_id": call.tool_call_id,
                    "tool_name": tool_name,
                    "args": args,
                    "row_count": row_count,
                    "table_name": args.get("table_name", "") if isinstance(args, dict) else "",
                })
                continue
            auto_calls.append(call)
            continue
        if tool_name in HUMAN_APPROVAL_TOOLS:
            pending_calls.append({
                "tool_call_id": call.tool_call_id,
                "tool_name": tool_name,
                "args": args,
            })
            continue
        auto_calls.append(call)

    return auto_calls, pending_calls


def _process_deferred_requests(
    session_id: str,
    run_id: str,
    message_history: list[ModelMessage],
    deferred: DeferredToolRequests,
    tracker: Any | None = None,
) -> dict[str, Any] | None:
    """Split deferred calls into auto-approved and human-approval groups.

    Returns an approval_request event if any calls require human confirmation.
    """
    _, pending_calls = _classify_deferred_calls(deferred)

    if pending_calls:
        request_id = uuid.uuid4().hex[:12]
        pending = PendingApproval(
            request_id=request_id,
            session_id=session_id,
            run_id=run_id,
            message_history=list(message_history),
            deferred_calls=pending_calls,
            tool_invocations=list(tracker.tool_invocations) if tracker else [],
        )
        get_pending_store().add(request_id, pending)

        return {
            "type": "approval_request",
            "run_id": run_id,
            "request_id": request_id,
            "calls": pending_calls,
        }

    return None
