from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from config.secrets import SUPPORTED_PROVIDERS, get_api_key

CACHE_TTL_SECONDS = 3600


def _cache_path(provider: str) -> Path:
    cache_dir = Path.home() / ".cache" / "scriptordb"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"models_{provider}.json"


def list_available_models(provider: str, *, use_cache: bool = True) -> list[str]:
    """从提供商的 API 动态获取可用模型列表，结果带本地缓存。"""
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    if use_cache:
        cached = _load_cache(provider)
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

    models = _parse_models(data)
    _save_cache(provider, models)
    return models


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


def _load_cache(provider: str) -> list[str] | None:
    path = _cache_path(provider)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - payload.get("ts", 0) > CACHE_TTL_SECONDS:
        return None
    models = payload.get("models")
    return models if isinstance(models, list) else None


def _save_cache(provider: str, models: list[str]) -> None:
    path = _cache_path(provider)
    try:
        path.write_text(json.dumps({"ts": time.time(), "models": models}))
    except OSError:
        pass


def resolve_model(provider: str, model: str | None) -> str:
    """解析出最终给 pydantic_ai 用的 'provider:model' 字符串。

    - 如果 model 已经是 'provider:' 前缀开头，原样返回
    - 如果没有指定，从可用模型中挑第一个
    - 支持模糊匹配（model 是子串）
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    config = SUPPORTED_PROVIDERS[provider]
    prefix = config.model_prefix

    if model:
        if model.startswith(prefix):
            return model
        if ":" in model:
            return model
        return f"{prefix}{model}"

    models = list_available_models(provider)
    if not models:
        raise RuntimeError(
            f"No models available for {provider}. "
            "Check API key or network, or pass --model explicitly."
        )
    return f"{prefix}{models[0]}"


def fuzzy_match_model(provider: str, query: str) -> str | None:
    """根据用户输入的子串在可用模型中查找匹配项。"""
    if not query:
        return None
    models = list_available_models(provider)
    q = query.lower()
    exact = [m for m in models if m.lower() == q]
    if exact:
        return exact[0]
    contains = [m for m in models if q in m.lower()]
    if len(contains) == 1:
        return contains[0]
    if contains:
        return contains[0]
    return None
