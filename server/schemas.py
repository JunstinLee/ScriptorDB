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


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    provider: str | None = None
    attachments: list[str] = Field(default_factory=list)


class SchemaColumn(BaseModel):
    name: str
    type: str
    pk: bool = False
    notnull: bool = False
    default_value: str | None = None
    autoincrement: bool = False


class SchemaTable(BaseModel):
    name: str
    sql: str
    columns: list[SchemaColumn] = Field(default_factory=list)


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    workspace_id: str | None = None
    workspace_name: str | None = None


class ModelsResponse(BaseModel):
    models: list[str]


class DefaultModelResponse(BaseModel):
    model: str | None


class CanonicalModelItem(BaseModel):
    slug: str
    display_name: str
    provider_specific_id: str | None = None
    available_providers: list[str] | None = None


class CanonicalModelsResponse(BaseModel):
    models: list[CanonicalModelItem]


class ModelEntry(BaseModel):
    provider_specific_id: str
    canonical_slug: str | None = None
    display_name: str | None = None


class ModelsWithCanonicalResponse(BaseModel):
    models: list[ModelEntry]


class ProviderInfo(BaseModel):
    name: str
    base_url: str


class SettingsResponse(BaseModel):
    llm_provider: str
    db_url: str
    llm_model: str | None
    default_models: dict[str, str]
    auto_restore_sessions: bool
    providers: list[ProviderInfo]
    providers_with_keys: list[str]
    workspace_id: str | None = None


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    default_model: str | None = None
    default_model_provider: str | None = None
    auto_restore_sessions: bool | None = None


class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str


class ApiKeyTestResponse(BaseModel):
    ok: bool
    error: str | None = None


class RunStartEvent(BaseModel):
    """SSE event: agent run started."""
    type: Literal["run_start"] = "run_start"
    run_id: str
    timestamp: str


class RunEndEvent(BaseModel):
    """SSE event: agent run ended."""
    type: Literal["run_end"] = "run_end"
    run_id: str
    timestamp: str


class TraceEvent(BaseModel):
    """SSE event: agent execution trace step."""
    type: Literal["trace"] = "trace"
    run_id: str
    step: int
    message: str
    timestamp: str


class ToolCallEvent(BaseModel):
    """SSE event: tool invocation started."""
    type: Literal["tool_call"] = "tool_call"
    run_id: str
    call_id: str
    tool_name: str
    args: dict[str, Any]
    timestamp: str


class ToolResultEvent(BaseModel):
    """SSE event: tool invocation completed."""
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
    """SSE event: incremental text token."""
    type: Literal["text_delta"] = "text_delta"
    run_id: str
    delta: str


class RunMetadataEvent(BaseModel):
    """SSE event: final metadata after run completes."""
    type: Literal["metadata"] = "metadata"
    run_id: str
    full_output: str
    canonical_slug: str | None = None
    display_name: str | None = None
    provider_specific_id: str | None = None


class ErrorEvent(BaseModel):
    """SSE event: user-facing error."""
    type: Literal["error"] = "error"
    message: str
    error_id: str | None = None


class WorkspaceCreateRequest(BaseModel):
    name: str | None = None
    path: str | None = None
    db_url: str | None = None


class WorkspaceActivateRequest(BaseModel):
    workspace_id: str | None = None


class WorkspaceItem(BaseModel):
    id: str
    name: str
    path: str
    created_at: str
    is_active: bool = False


class WorkspaceDetail(WorkspaceItem):
    db_url: str
    llm_provider: str
    llm_model: str | None = None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceItem]
    active_workspace_id: str | None = None


class ActiveWorkspaceResponse(BaseModel):
    workspace: WorkspaceDetail | None = None


class WorkspaceDeleteResponse(BaseModel):
    ok: bool
    deleted_files: bool = False
