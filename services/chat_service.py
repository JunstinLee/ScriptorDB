from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelMessage

from server.schemas import StoredRun, StoredToolInvocation
from server.sessions import get_session_store


def persist_chat_run(
    session_id: str,
    new_messages_collector: list[ModelMessage],
    run_collector: dict[str, Any],
) -> None:
    print(f"[CANCEL_TRACE] PERSIST_ENTER session_id={session_id} run_id={run_collector.get('run_id')} status={run_collector.get('status')} tool_count={len(run_collector.get('tool_invocations',[]))} msg_count={len(new_messages_collector)} final_output={str(run_collector.get('final_output',''))[:50]}")
    session = get_session_store().get(session_id)
    if session is None:
        print("[CANCEL_TRACE] PERSIST_SESSION_NOT_FOUND")
        return

    if new_messages_collector:
        session.add_model_messages(new_messages_collector)
        print(f"[CANCEL_TRACE] PERSIST_ADDED_MODEL_MSGS count={len(new_messages_collector)}")

    if run_collector.get("status") == "completed" and run_collector.get("final_output"):
        session.add_assistant_message(run_collector["final_output"])
        print(f"[CANCEL_TRACE] PERSIST_ADDED_ASSISTANT_MSG content={run_collector['final_output'][:50]}")

    if run_collector:
        run = StoredRun(
            run_id=run_collector["run_id"],
            status=run_collector["status"],
            tool_invocations=[
                StoredToolInvocation(**inv)
                for inv in run_collector.get("tool_invocations", [])
            ],
            final_output=run_collector.get("final_output", ""),
            started_at=run_collector["started_at"],
            ended_at=run_collector.get("ended_at"),
            error_message=run_collector.get("error_message"),
        )
        session.add_run(run)
        get_session_store().save()
        print(f"[CANCEL_TRACE] PERSIST_SAVED run_id={run.run_id} status={run.status} tool_ids={[t.call_id for t in run.tool_invocations]} tool_statuses={[t.status for t in run.tool_invocations]}")
