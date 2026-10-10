from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ApiKeyStatusKind = Literal["missing", "valid", "invalid", "unknown", "no_workspace"]


class ProviderInfo(BaseModel):
    name: str
    base_url: str


class SettingsResponse(BaseModel):
    llm_provider: str
    db_url: str
    llm_model: str | None
    default_models: dict[str, str]
    auto_restore_sessions: bool
    browser_enabled: bool = False
    locale: str = ""
    providers: list[ProviderInfo]
    providers_with_keys: list[str]
    workspace_id: str | None = None


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    default_model: str | None = None
    default_model_provider: str | None = None
    auto_restore_sessions: bool | None = None
    browser_enabled: bool | None = None
    locale: str | None = None


class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str


class ApiKeyTestResponse(BaseModel):
    ok: bool
    error: str | None = None


class ApiKeyStatus(BaseModel):
    """Result of an active API key check. Never carries the key itself."""

    provider: str
    status: ApiKeyStatusKind
    error: str | None = None
    checked_at: str
