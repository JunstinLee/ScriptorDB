from __future__ import annotations

from typing import Any

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config.secrets import SUPPORTED_PROVIDERS, get_api_key

OPENAI_COMPAT_PROVIDERS = {"nim", "together"}


def build_model(provider: str, model_name: str, workspace_id: str | None) -> Any:
    if provider in OPENAI_COMPAT_PROVIDERS:
        api_key = get_api_key(provider, workspace_id)
        provider_cfg = SUPPORTED_PROVIDERS[provider]
        name = model_name.split(":", 1)[-1]
        return OpenAIChatModel(
            name,
            provider=OpenAIProvider(base_url=provider_cfg.base_url, api_key=api_key),
        )
    return model_name
