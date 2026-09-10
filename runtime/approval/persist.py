from __future__ import annotations

"""取消接管终态的落盘归档（runtime 层，供编排器调用）。

原位于 services/session_service.py；该函数只操作 runtime 类型
（SessionStore / PendingTakeover）与 schemas DTO，不依赖业务服务层，
迁入 runtime 消除 runtime → services → runtime 的层环。
"""

from typing import Any

from runtime.approval.store import PendingTakeover
from runtime.run_tracker import utc_now_iso
from runtime.session_model import SessionStore
from schemas import StoredRun, StoredToolInvocation


def persist_cancelled_takeover(
    session_store: SessionStore,
    session_id: str,
    checkpoint: PendingTakeover,
) -> bool:
    """把被取消接管的 checkpoint 归档为 cancelled run。

    checkpoint 中记录的 turn 消息与工具调用一并落盘，作为取消终态。
    返回是否存在对应 session 并完成落盘（无 session 时静默跳过）。
    """
    session = session_store.get(session_id)
    if session is None:
        return False
    if checkpoint.turn_new_messages:
        session.add_model_messages(list(checkpoint.turn_new_messages))
    run = StoredRun(
        run_id=checkpoint.run_id,
        status="cancelled",
        tool_invocations=[
            StoredToolInvocation(**inv)
            for inv in checkpoint.tool_invocations
        ],
        final_output=checkpoint.final_output,
        started_at=checkpoint.created_at,
        ended_at=utc_now_iso(),
    )
    session.add_run(run)
    session_store.save()
    return True


def persist_abandoned_approval(
    session_store: SessionStore,
    session_id: str,
    run_id: str,
    tool_invocations: list[dict[str, Any]],
    final_output: str,
    new_messages: list[Any],
) -> bool:
    """把断连丢弃的审批挂起 run 归档为 cancelled run。

    与 persist_cancelled_takeover 并列的终态落盘入口。用户主动取消审批的路径
    不调用本函数：那条路径原 SSE 流仍活着，落盘由 persist_chat_run 负责；
    只有断连（原流已死、后续无人落盘）才必须在此自行归档——该不对称是有意为之。

    返回是否存在对应 session 并完成落盘（无 session 时静默跳过）。
    """
    session = session_store.get(session_id)
    if session is None:
        return False
    if new_messages:
        session.add_model_messages(list(new_messages))
    # PendingApproval 快照不带 run 起始时间，取消时刻即归档时刻
    run = StoredRun(
        run_id=run_id,
        status="cancelled",
        tool_invocations=[
            StoredToolInvocation(**inv) for inv in tool_invocations
        ],
        final_output=final_output,
        started_at=utc_now_iso(),
        ended_at=utc_now_iso(),
    )
    session.add_run(run)
    session_store.save()
    return True
