from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelMessage

from core.logging_setup import get_logger
from schemas import StoredRun, StoredToolInvocation
from server.sessions import get_session_store

logger = get_logger("chat_service")


def persist_chat_run(
    session_id: str,
    new_messages_collector: list[ModelMessage],
    run_collector: dict[str, Any],
) -> None:
    session = get_session_store().get(session_id)
    if session is None:
        logger.warning(
            "persist_chat_run skipped: session not in store session_id=%s run_id=%s",
            session_id, run_collector.get("run_id", ""),
        )
        return
    logger.info(
        "persist_chat_run start session_id=%s run_id=%s status=%s "
        "new_messages=%s final_output_len=%s tool_invocations=%s",
        session_id, run_collector.get("run_id", ""), run_collector.get("status"),
        len(new_messages_collector), len(run_collector.get("final_output", "")),
        len(run_collector.get("tool_invocations", [])),
    )

    if new_messages_collector:
        session.add_model_messages(new_messages_collector)

    if run_collector.get("status") == "completed" and run_collector.get("final_output"):
        session.add_assistant_message(run_collector["final_output"])

    if run_collector:
        try:
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
        except Exception:
            logger.exception(
                "persist_chat_run StoredRun construction failed session_id=%s run_id=%s "
                "tool_invocations=%r",
                session_id, run_collector.get("run_id", ""),
                run_collector.get("tool_invocations", []),
            )
            raise
        session.add_run(run)
        logger.info("persist_chat_run adding run, saving store session_id=%s", session_id)
        get_session_store().save()
        logger.info("persist_chat_run done session_id=%s messages=%s runs=%s", session_id, len(session.messages), len(session.runs))

