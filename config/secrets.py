from __future__ import annotations

import keyring

SERVICE = "ScriptorDB"


def get_api_key(provider: str) -> str | None:
    return keyring.get_password(SERVICE, provider)


def save_api_key(provider: str, key: str) -> None:
    keyring.set_password(SERVICE, provider, key)


def delete_api_key(provider: str) -> None:
    keyring.delete_password(SERVICE, provider)


SUPPORTED_PROVIDERS: dict[str, str] = {
    "openai": "openai:gpt-4.1",
    "anthropic": "anthropic:claude-sonnet-4-6",
    "google": "google:gemini-2.5-flash",
    "groq": "groq:llama-4-scout-17b-16e-instruct",
    "mistral": "mistral:mistral-large-latest",
    "nvidia": "nvidia:meta/llama-3.1-70b-instruct",
}
