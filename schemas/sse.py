from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class RunStartEvent(BaseModel):
    type: Literal["run_start"] = "run_start"
    run_id: str
    timestamp: str


class RunEndEvent(BaseModel):
    type: Literal["run_end"] = "run_end"
    run_id: str
    timestamp: str


class TraceEvent(BaseModel):
    type: Literal["trace"] = "trace"
    run_id: str
    step: int
    message: str
    timestamp: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    run_id: str
    call_id: str
    tool_name: str
    args: dict[str, Any]
    timestamp: str


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    run_id: str
    call_id: str
    tool_name: str
    success: bool
    output: str | None = None
    error_code: str | None = None
    duration_ms: int | None = None
    data: dict[str, Any] | None = None
    timestamp: str


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    run_id: str
    delta: str


class RunMetadataEvent(BaseModel):
    type: Literal["metadata"] = "metadata"
    run_id: str
    full_output: str
    canonical_slug: str | None = None
    display_name: str | None = None
    provider_specific_id: str | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    error_id: str | None = None


class ApprovalRequestEvent(BaseModel):
    type: Literal["approval_request"] = "approval_request"
    run_id: str
    request_id: str
    calls: list[dict[str, Any]]
