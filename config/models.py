from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from config.canonical_models import (
    CANONICAL_REGISTRY,
    get_canonical_by_slug,
    get_canonical_for_provider,
    get_canonical_for_provider_model,
)
from config.secrets import SUPPORTED_PROVIDERS, get_api_key

CACHE_TTL_SECONDS = 3600

EXCLUDE_KEYWORDS = [
    "embedding",
    "embed",
    "tts",
    "speech",
    "whisper",
    "audio",
    "moderation",
    "rerank",
]

def _cache_path(provider: str) -> Path:
    from platformdirs import user_cache_dir

    old_path = Path.home() / ".cache" / "scriptordb"
    if old_path.exists():
        cache_dir = old_path
    else:
        cache_dir = Path(user_cache_dir("scriptordb", ensure_exists=True))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"models_{provider}.json"


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

    raw = _parse_models(data)
    models = filter_chat_models(raw)
    _save_cache(provider, models)
    return models


def get_recommended_models(provider: str) -> list[str]:
    """获取 provider 的推荐模型列表（返回 provider 特定的模型 ID）。

    优先基于 Canonical Model Registry：
    1. 遍历 CANONICAL_REGISTRY，筛选出该 provider 有 alias 的模型
    2. 优先精确匹配 alias 是否在 provider 实际可用模型列表中
    3. 否则做子串匹配（alias 在 model_id 中），用于处理日期/版本后缀变体

    降级路径：当 Canonical Registry 中没有命中时，使用 RECOMMENDED_FALLBACK
    列表（基于 slug 的子串匹配）。
    """
    try:
        models = list_available_models(provider)
    except Exception:
        models = []

    models_lower = {m.lower(): m for m in models}
    recommended: list[str] = []
    seen: set[str] = set()

    for canonical in CANONICAL_REGISTRY:
        alias = canonical.aliases.get(provider)
        if not alias:
            continue
        match = models_lower.get(alias.lower())
        if match and match not in seen:
            recommended.append(match)
            seen.add(match)
            continue
        for model in models:
            if alias.lower() in model.lower() and model not in seen:
                recommended.append(model)
                seen.add(model)
                break

    return recommended


def list_canonical_models(provider: str | None = None) -> list[dict]:
    """返回 Canonical Model 列表（字典形式，便于序列化）。

    如果指定 provider，仅返回该 provider 有 alias 的模型，
    并在每条记录中附加 `provider_specific_id` 字段。
    """
    if provider:
        items = get_canonical_for_provider(provider)
    else:
        items = list(CANONICAL_REGISTRY)

    result: list[dict] = []
    for m in items:
        entry: dict = {
            "slug": m.slug,
            "display_name": m.display_name,
        }
        if provider:
            entry["provider_specific_id"] = m.aliases.get(provider)
        else:
            entry["available_providers"] = list(m.aliases.keys())
        result.append(entry)
    return result


def resolve_canonical_slug(provider: str, model_id: str) -> str | None:
    """从 provider 的实际模型 ID 反向推断其 canonical slug。

    用途：会话记录、日志、跨 Provider 对比时统一模型身份。
    """
    canonical = get_canonical_for_provider_model(provider, model_id)
    return canonical.slug if canonical else None


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
