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
    family: str
    display_name: str
    description: str = ""
    tags: list[str] = []
    provider_specific_id: str | None = None
    available_providers: list[str] | None = None


class CanonicalModelsResponse(BaseModel):
    models: list[CanonicalModelItem]


class ModelEntry(BaseModel):
    """带 Canonical 信息的模型条目（前端可同时拿到 display_name 和原始 ID）。"""

    provider_specific_id: str
    canonical_slug: str | None = None
    display_name: str | None = None
    family: str | None = None


class ModelsWithCanonicalResponse(BaseModel):
    models: list[ModelEntry]
