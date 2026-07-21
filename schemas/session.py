from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str


class MessageItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    attachments: list[str] = Field(default_factory=list)
    crawl_url: str | None = None


class StoredToolInvocation(BaseModel):
    call_id: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: Literal["running", "success", "error"] = "running"
    output: str | None = None
    error_code: str | None = None
    duration_ms: int | None = None
    data: dict[str, Any] | None = None
    started_at: str
    ended_at: str | None = None


class StoredRun(BaseModel):
    run_id: str
    status: Literal["running", "completed", "error"] = "running"
    tool_invocations: list[StoredToolInvocation] = Field(default_factory=list)
    trace_steps: list[Any] = Field(default_factory=list)
    final_output: str = ""
    started_at: str
    ended_at: str | None = None
    error_message: str | None = None


class SessionInfo(BaseModel):
    session_id: str
    messages: list[MessageItem]
    runs: list[StoredRun] = Field(default_factory=list)
    created_at: datetime


class SessionListItem(BaseModel):
    session_id: str
    created_at: datetime
    last_access: datetime
    message_count: int
    title: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]
