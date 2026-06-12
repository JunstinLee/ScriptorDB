from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalModel:
    """跨 Provider 统一的模型定义。

    Attributes:
        slug: 全局唯一主键（如 "deepseek-v4-pro"），推荐/排序都基于此。
        display_name: 用户面向的展示名（如 "DeepSeek V4 Pro"）。
        aliases: provider -> 该 provider 的实际模型 ID。
                 provider 名需与 config.secrets.SUPPORTED_PROVIDERS 一致。
    """

    slug: str
    display_name: str
    aliases: dict[str, str] = field(default_factory=dict)


CANONICAL_REGISTRY: tuple[CanonicalModel, ...] = (
    # ========== OpenAI ==========
    CanonicalModel(
        slug="gpt-5.5",
        display_name="GPT-5.5",
        aliases={
            "openai": "gpt-5.5",
            "openrouter": "gpt-5.5",
            "together": "gpt-5.5",
        },
    ),
    CanonicalModel(
        slug="gpt-5.5-pro",
        display_name="GPT-5.5 Pro",
        aliases={
            "openai": "gpt-5.5-pro",
            "openrouter": "gpt-5.5-pro",
            "together": "gpt-5.5-pro",
        },
    ),
    CanonicalModel(
        slug="gpt-5.5-thinking",
        display_name="GPT-5.5 Thinking",
        aliases={
            "openai": "gpt-5.5-thinking",
            "openrouter": "gpt-5.5-thinking",
            "together": "gpt-5.5-thinking",
        },
    ),
    CanonicalModel(
        slug="gpt-5.5-instant",
        display_name="GPT-5.5 Instant",
        aliases={
            "openai": "gpt-5.5-instant",
            "openrouter": "gpt-5.5-instant",
            "together": "gpt-5.5-instant",
        },
    ),
    # ========== Anthropic ==========
    CanonicalModel(
        slug="claude-opus-4-8",
        display_name="Claude Opus 4-8",
        aliases={
            "anthropic": "claude-opus-4-8",
            "openrouter": "claude-opus-4-8",
            "together": "claude-opus-4-8",
        },
    ),
    CanonicalModel(
        slug="claude-opus-4-7",
        display_name="Claude Opus 4-7",
        aliases={
            "anthropic": "claude-opus-4-7",
            "openrouter": "claude-opus-4-7",
            "together": "claude-opus-4-7",
        },
    ),
    CanonicalModel(
        slug="claude-sonnet-4-6",
        display_name="Claude Sonnet 4-6",
        aliases={
            "anthropic": "claude-sonnet-4-6",
            "openrouter": "claude-sonnet-4-6",
            "together": "claude-sonnet-4-6",
        },
    ),
    CanonicalModel(
        slug="claude-haiku-4-5",
        display_name="Claude Haiku 4-5",
        aliases={
            "anthropic": "claude-haiku-4-5",
            "openrouter": "claude-haiku-4-5",
            "together": "claude-haiku-4-5",
        },
    ),
    # ========== Google ==========
    CanonicalModel(
        slug="gemini-3.5-flash",
        display_name="Gemini 3.5 Flash",
        aliases={
            "google": "gemini-3.5-flash",
            "openrouter": "gemini-3.5-flash",
            "together": "gemini-3.5-flash",
        },
    ),
    CanonicalModel(
        slug="gemini-3.1-pro",
        display_name="Gemini 3.1 Pro",
        aliases={
            "google": "gemini-3.1-pro",
            "openrouter": "gemini-3.1-pro",
            "together": "gemini-3.1-pro",
        },
    ),
    CanonicalModel(
        slug="gemini-3.1-flash-lite",
        display_name="Gemini 3.1 Flash Lite",
        aliases={
            "google": "gemini-3.1-flash-lite",
            "openrouter": "gemini-3.1-flash-lite",
            "together": "gemini-3.1-flash-lite",
        },
    ),
    CanonicalModel(
        slug="gemini-3-flash",
        display_name="Gemini 3 Flash",
        aliases={
            "google": "gemini-3-flash",
            "openrouter": "gemini-3-flash",
            "together": "gemini-3-flash",
        },
    ),
    # ========== Groq / Together / OpenRouter / NIM (shared) ==========
    CanonicalModel(
        slug="kimi-2.6",
        display_name="Kimi 2.6",
        aliases={
            "groq": "kimi-2.6",
            "nim": "kimi-k2.6",
            "openrouter": "kimi-2.6",
            "together": "kimi-2.6",
        },
    ),
    CanonicalModel(
        slug="kimi-2.5",
        display_name="Kimi 2.5",
        aliases={
            "groq": "kimi-2.5",
            "openrouter": "kimi-2.5",
            "together": "kimi-2.5",
        },
    ),
    CanonicalModel(
        slug="glm-5.1",
        display_name="GLM 5.1",
        aliases={
            "groq": "glm-5.1",
            "openrouter": "glm-5.1",
            "together": "glm-5.1",
        },
    ),
    CanonicalModel(
        slug="minimax-2.7",
        display_name="MiniMax 2.7",
        aliases={
            "groq": "minimax-2.7",
            "openrouter": "minimax-2.7",
            "nim": "minimax-m2.7",
            "together": "minimax-2.7",
        },
    ),
    CanonicalModel(
        slug="deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
        aliases={
            "groq": "deepseek-v4-pro",
            "openrouter": "deepseek-v4-pro",
            "nim": "deepseek-v4-pro",
            "together": "deepseek-v4-pro",
        },
    ),
    CanonicalModel(
        slug="deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        aliases={
            "groq": "deepseek-v4-flash",
            "openrouter": "deepseek-v4-flash",
            "nim": "deepseek-v4-flash",
            "together": "deepseek-v4-flash",
        },
    ),
    CanonicalModel(
        slug="mimo-v2.5-pro",
        display_name="Mimo 2.5 Pro",
        aliases={
            "groq": "mimo-v2.5-pro",
            "openrouter": "mimo-v2.5-pro",
            "together": "mimo-v2.5-pro",
        },
    ),
    CanonicalModel(
        slug="mimo-v2.5",
        display_name="Mimo 2.5",
        aliases={
            "groq": "mimo-v2.5",
            "openrouter": "mimo-v2.5",
            "together": "mimo-v2.5",
        },
    ),
    CanonicalModel(
        slug="minimax-m3",
        display_name="MiniMax M3",
        aliases={
            "groq": "minimax-m3",
            "mistral": "minimax-m3",
            "openrouter": "minimax-m3",
            "together": "minimax-m3",
        },
    ),
    # ========== Mistral only ==========
    CanonicalModel(
        slug="mistral-medium-3.5",
        display_name="Mistral Medium 3.5",
        aliases={
            "mistral": "mistral-medium-3.5",
        },
    ),
    CanonicalModel(
        slug="mistral-small-4",
        display_name="Mistral Small 4",
        aliases={
            "mistral": "mistral-small-4",
        },
    ),
    CanonicalModel(
        slug="mistral-large-3",
        display_name="Mistral Large 3",
        aliases={
            "mistral": "mistral-large-3",
        },
    ),
    # ========== NIM only ==========
    CanonicalModel(
        slug="glm-5",
        display_name="GLM 5",
        aliases={
            "nim": "glm-5",
        },
    ),
)


def get_canonical_by_slug(slug: str) -> CanonicalModel | None:
    """根据 slug 查找 CanonicalModel，未找到返回 None。"""
    for m in CANONICAL_REGISTRY:
        if m.slug == slug:
            return m
    return None


def _strip_date_suffix(name: str) -> str:
    """剥离模型 ID 中常见的日期后缀与版本后缀。

    例如 'gpt-5-mini-2025' -> 'gpt-5-mini'，'claude-sonnet-4-20250514' -> 'claude-sonnet-4'。
    兼容的格式：尾部 -YYYYMMDD、-YYYY-MM-DD、-vN、-N（数字版本号）。
    """
    import re

    return re.sub(
        r"[-_](?:\d{8}|\d{4}[-_]?\d{2}[-_]?\d{2}|v\d+|\d+)$",
        "",
        name,
    )


def _strip_provider_prefix(name: str) -> str:
    """剥离常见的 provider 前缀（如 'openai/'、'google/'）。"""
    if "/" in name:
        return name.split("/", 1)[1]
    return name


def get_canonical_for_provider_model(provider: str, model_id: str) -> CanonicalModel | None:
    """反向解析：给定 provider 和该 provider 的模型 ID，返回匹配的 CanonicalModel。

    匹配策略（按优先级）：
    1. 精确匹配 aliases[provider]
    2. 剥离 provider 前缀与日期后缀后精确匹配 aliases[provider]
    3. 子串匹配 aliases[provider] 或 slug
    4. 跨 provider 的 alias 完全相等（兜底，例如某些聚合平台会引用官方 ID）

    用于在收到模型列表后推断其 Canonical 等价物。
    """
    if not model_id:
        return None

    lower = model_id.lower()

    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() == lower:
            return m

    base = _strip_date_suffix(_strip_provider_prefix(model_id)).lower()
    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() == base:
            return m

    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() in lower:
            return m
        if m.slug.lower() in lower:
            return m

    for m in CANONICAL_REGISTRY:
        for other_provider, other_alias in m.aliases.items():
            if other_alias and other_alias.lower() == lower:
                return m

    return None


def get_canonical_for_provider(provider: str) -> list[CanonicalModel]:
    """返回所有在指定 provider 下有 alias 的 CanonicalModel。"""
    return [m for m in CANONICAL_REGISTRY if provider in m.aliases]
