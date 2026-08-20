from __future__ import annotations

from typing import Any

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

from runtime.run_tracker import utc_now_iso


def strip_leading_user_prompt(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Drop the leading prompt turn from new_messages.

    pydantic-ai prepends the prompt as a UserPromptPart-only ModelRequest;
    the runner only forwards the messages that follow it.
    """
    if (
        messages
        and isinstance(messages[0], ModelRequest)
        and all(isinstance(p, UserPromptPart) for p in messages[0].parts)
    ):
        return messages[1:]
    return messages


def new_messages_event(run_id: str, messages: list[ModelMessage]) -> dict[str, Any]:
    return {"type": "new_messages", "run_id": run_id, "messages": messages}


def deferred_requests_event(
    run_id: str,
    deferred: DeferredToolRequests,
    all_messages: list[ModelMessage],
) -> dict[str, Any]:
    return {
        "type": "_deferred_tool_requests",
        "run_id": run_id,
        "deferred": deferred,
        "all_messages": all_messages,
    }


def metadata_event(run_id: str, full_output: str) -> dict[str, Any]:
    return {"type": "metadata", "run_id": run_id, "full_output": full_output}


def run_end_event(run_id: str) -> dict[str, Any]:
    return {"type": "run_end", "run_id": run_id, "timestamp": utc_now_iso()}


def error_event(
    run_id: str,
    error_id: str,
    rate_limit: tuple[int, str] | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "error",
        "run_id": run_id,
        "message": f"Run failed (ID: {error_id})",
        "error_id": error_id,
    }
    if detail:
        event["message"] = f"Run failed (ID: {error_id}): {detail}"
    if rate_limit is not None:
        status_code, model_name = rate_limit
        event["error_type"] = "rate_limit"
        event["status_code"] = status_code
        event["model_name"] = model_name
        event["message"] = (
            "Rate limited (HTTP 429 Too Many Requests): too many requests. "
            "Try again shortly."
        )
    return event
