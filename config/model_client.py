from __future__ import annotations

from typing import Protocol

import httpx

from config.model_cache import load_cache, save_cache
from config.secrets import SUPPORTED_PROVIDERS, get_api_key

EXCLUDE_KEYWORDS = [
    "embedding", "embed", "tts", "speech",
    "whisper", "audio", "moderation", "rerank",
]


class ModelFetcher(Protocol):
    def __call__(self, provider: str, *, use_cache: bool = True) -> list[str]: ...


def _parse_models(data: dict) -> list[str]:
    if "data" in data and isinstance(data["data"], list):
        ids: set[str] = {m["id"] for m in data["data"] if isinstance(m, dict) and m.get("id")}
        if ids:
            return sorted(ids)
    if "models" in data and isinstance(data["models"], list):
        raw = [
            m.get("name") or m.get("id")
            for m in data["models"]
            if isinstance(m, dict) and (m.get("name") or m.get("id"))
        ]
        ids = {x for x in raw if isinstance(x, str)}
        if ids:
            return sorted(ids)
    return []


def filter_chat_models(models: list[str]) -> list[str]:
    result = []
    for model in models:
        name = model.lower()
        if any(k in name for k in EXCLUDE_KEYWORDS):
            continue
        result.append(model)
    return result


def list_available_models(provider: str, *, use_cache: bool = True) -> list[str]:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    if use_cache:
        cached = load_cache(provider)
        if cached is not None:
            return cached

    config = SUPPORTED_PROVIDERS[provider]
    api_key = get_api_key(provider)
    if not api_key:
        raise RuntimeError(f"No API key for {provider}. Run 'python main.py setup' first.")

    url = f"{config.base_url.rstrip('/')}{config.list_models_path}"
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = httpx.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    raw = _parse_models(data)
    models = filter_chat_models(raw)
    save_cache(provider, models)
    return models
