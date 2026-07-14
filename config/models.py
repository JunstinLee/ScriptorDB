from __future__ import annotations

from config.canonical_models import (
    CANONICAL_REGISTRY,
    get_canonical_by_slug,
    get_canonical_for_provider,
    get_canonical_for_provider_model,
)
from config.model_client import list_available_models
from config.secrets import SUPPORTED_PROVIDERS


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
