from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from config.app_config import AppConfig


def utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunTracker:
    """管理单个 agent run 的元数据：tool_invocations, final_output, status。"""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tool_start_times: dict[str, float] = field(default_factory=dict)
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: str | None = None
    error_message: str | None = None
    status: str = "running"

    def to_run_collector(self) -> dict[str, Any]:
        print(f"[run_tracker] to_run_collector: run_id={self.run_id} status={self.status} tools={[(t['call_id'],t['status'],t['tool_name']) for t in self.tool_invocations]}")
        return {
            "run_id": self.run_id,
            "status": self.status,
            "tool_invocations": self.tool_invocations,
            "final_output": self.final_output,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error_message": self.error_message,
        }

    def start_tool(self, call_id: str) -> None:
        self.tool_start_times[call_id] = time.monotonic()

    def tool_duration_ms(self, call_id: str) -> int | None:
        start = self.tool_start_times.pop(call_id, None)
        if start is None:
            return None
        return int((time.monotonic() - start) * 1000)

    def add_tool_invocation(
        self, call_id: str, tool_name: str, args: dict
    ) -> None:
        print(f"[run_tracker] add_tool: run_id={self.run_id} call_id={call_id} tool={tool_name}")
        self.tool_invocations.append({
            "call_id": call_id,
            "tool_name": tool_name,
            "args": args,
            "status": "running",
            "started_at": utc_now_iso(),
        })

    def complete_tool(
        self,
        call_id: str,
        success: bool,
        output: Any,
        error_code: str | None,
        duration_ms: int | None,
        data: dict[str, Any] | None = None,
    ) -> None:
        print(f"[run_tracker] complete_tool: run_id={self.run_id} call_id={call_id} success={success} output={str(output)[:80] if output else None}")
        for inv in self.tool_invocations:
            if inv["call_id"] == call_id:
                inv["status"] = "success" if success else "error"
                inv["output"] = output
                inv["error_code"] = error_code
                inv["duration_ms"] = duration_ms
                inv["data"] = data
                inv["ended_at"] = utc_now_iso()
                return

    def append_text(self, delta: str) -> None:
        self.final_output += delta

    def finish(self) -> None:
        self.status = "completed"
        self.ended_at = utc_now_iso()

    def fail(self, message: str) -> None:
        self.status = "error"
        self.error_message = message
        self.ended_at = utc_now_iso()
