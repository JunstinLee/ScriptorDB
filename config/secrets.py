from __future__ import annotations

from dataclasses import dataclass

import keyring

SERVICE = "ScriptorDB"


def get_api_key(provider: str) -> str | None:
    return keyring.get_password(SERVICE, provider)


def save_api_key(provider: str, key: str) -> None:
    keyring.set_password(SERVICE, provider, key)


def delete_api_key(provider: str) -> None:
    keyring.delete_password(SERVICE, provider)


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
}
