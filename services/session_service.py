from __future__ import annotations

"""会话业务服务：run / 消息的落盘归档。

与 runtime/ 存储层解耦：编排器等调用方只调用服务方法，
不直接操作 Session 结构或存储实现。
"""

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
