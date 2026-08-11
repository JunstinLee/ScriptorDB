from __future__ import annotations

import json as json_mod
from typing import Any

from tools.tool_result import ToolResult

from server.run_tracker import utc_now_iso


def parse_tool_args(args: Any) -> dict[str, Any]:
    """Normalize a tool call's raw args into a dict for events and tracking.

    String args are JSON-parsed; anything that is not a dict is wrapped as
    {"raw": str(args)}.
    """
    if isinstance(args, str):
        try:
            args = json_mod.loads(args)
        except json_mod.JSONDecodeError:
            args = {"raw": args}
    return args if isinstance(args, dict) else {"raw": str(args)}


def normalize_tool_content(
    content: Any,
) -> tuple[bool, Any, str | None, dict[str, Any] | None]:
    """Normalize a FunctionToolResultEvent part content into a 4-tuple.

    Returns (success, output, error_code, data). ToolResult is decomposed into
    its fields; str/dict contents are kept / JSON-encoded as output.
    """
    success = True
    output: Any = None
    error_code: str | None = None
    data: dict[str, Any] | None = None
    if isinstance(content, ToolResult):
        success = content.success
        output = content.output
        data = content.data
        if content.error:
            error_code = content.error.category
            output = content.error.message
    elif isinstance(content, str):
        output = content
    elif isinstance(content, dict):
        output = json_mod.dumps(content, ensure_ascii=False)
    return success, output, error_code, data


def run_start_event(run_id: str) -> dict[str, Any]:
    return {"type": "run_start", "run_id": run_id, "timestamp": utc_now_iso()}


def tool_call_event(
    run_id: str,
    call_id: str,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "tool_call",
        "run_id": run_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "args": args,
        "timestamp": utc_now_iso(),
    }


def tool_result_event(
    run_id: str,
    call_id: str,
    tool_name: str,
    success: bool,
    output: Any,
    error_code: str | None,
    duration_ms: int | None,
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "run_id": run_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "success": success,
        "output": output,
        "error_code": error_code,
        "duration_ms": duration_ms,
        "data": data,
        "timestamp": utc_now_iso(),
    }


def text_delta_event(run_id: str, delta: str) -> dict[str, Any]:
    return {"type": "text_delta", "run_id": run_id, "delta": delta}


def trace_event(run_id: str, step: int, message: str) -> dict[str, Any]:
    return {
        "type": "trace",
        "run_id": run_id,
        "step": step,
        "message": message,
        "timestamp": utc_now_iso(),
    }


def browser_action_event(
    *,
    run_id: str,
    tool: str,
    selector: str,
    coords: dict[str, Any],
    success: bool,
    detail: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "type": "browser_action",
        "run_id": run_id,
        "tool": tool,
        "selector": selector,
        "coords": coords,
        "success": success,
        "detail": detail,
        "timestamp": timestamp,
    }


def human_takeover_request_event(
    *,
    run_id: str,
    checkpoint_id: str,
    reason: str,
    trigger: str,
    current_url: str,
    screenshot_available: bool,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "type": "human_takeover_request",
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "reason": reason,
        "trigger": trigger,
        "current_url": current_url,
        "screenshot_available": screenshot_available,
        "timestamp": timestamp,
    }
