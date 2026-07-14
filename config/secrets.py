from __future__ import annotations

from dataclasses import dataclass

import keyring

LEGACY_SERVICE = "ScriptorDB"


def _service(workspace_id: str | None) -> str:
    if workspace_id:
        return f"scriptordb:{workspace_id}"
    return LEGACY_SERVICE


def get_api_key(provider: str, workspace_id: str | None = None) -> str | None:
    value = keyring.get_password(_service(workspace_id), provider)
    if value is None and workspace_id is not None:
        value = keyring.get_password(LEGACY_SERVICE, provider)
    return value


def save_api_key(provider: str, key: str, workspace_id: str | None = None) -> None:
    keyring.set_password(_service(workspace_id), provider, key)


def _safe_delete(service: str, provider: str) -> None:
    try:
        keyring.delete_password(service, provider)
    except Exception:
        pass


def delete_api_key(provider: str, workspace_id: str | None = None) -> None:
    _safe_delete(_service(workspace_id), provider)
    if workspace_id is not None:
        _safe_delete(LEGACY_SERVICE, provider)


def has_api_key(provider: str, workspace_id: str | None = None) -> bool:
    return get_api_key(provider, workspace_id) is not None


MYSQL_PASSWORD_USERNAME = "mysql_password"


def get_mysql_password(workspace_id: str) -> str | None:
    return keyring.get_password(_service(workspace_id), MYSQL_PASSWORD_USERNAME)


def save_mysql_password(workspace_id: str, password: str) -> None:
    keyring.set_password(_service(workspace_id), MYSQL_PASSWORD_USERNAME, password)


def delete_mysql_password(workspace_id: str) -> None:
    _safe_delete(_service(workspace_id), MYSQL_PASSWORD_USERNAME)


def has_mysql_password(workspace_id: str) -> bool:
    return get_mysql_password(workspace_id) is not None


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    list_models_path: str
    model_prefix: str


SUPPORTED_PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        base_url="https://api.openai.com/v1",
        list_models_path="/models",
        model_prefix="openai:",
    ),
    "anthropic": ProviderConfig(
        base_url="https://api.anthropic.com",
        list_models_path="/v1/models",
        model_prefix="anthropic:",
    ),
    "google": ProviderConfig(
        base_url="https://generativelanguage.googleapis.com",
        list_models_path="/v1beta/models",
        model_prefix="google:",
    ),
    "groq": ProviderConfig(
        base_url="https://api.groq.com/openai/v1",
        list_models_path="/models",
        model_prefix="groq:",
    ),
    "mistral": ProviderConfig(
        base_url="https://api.mistral.ai/v1",
        list_models_path="/models",
        model_prefix="mistral:",
    ),
    "openrouter": ProviderConfig(
        base_url="https://openrouter.ai/api/v1",
        list_models_path="/models",
        model_prefix="openrouter:",
    ),
    "nim": ProviderConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        list_models_path="/models",
        model_prefix="openai:",
    ),
    "together": ProviderConfig(
        base_url="https://api.together.xyz/v1",
        list_models_path="/models",
        model_prefix="openai:",
    ),
}
