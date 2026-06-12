from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str


class MessageItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionInfo(BaseModel):
    session_id: str
    messages: list[MessageItem]
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


class SchemaTable(BaseModel):
    name: str
    sql: str


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str


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
    """带 Canonical 信息的模型条目（前端可同时拿到 display_name 和原始 ID）。"""

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


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    default_model: str | None = None
    auto_restore_sessions: bool | None = None


class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str


class ApiKeyTestResponse(BaseModel):
    ok: bool
    error: str | None = None
