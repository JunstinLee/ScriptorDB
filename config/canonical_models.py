"""Canonical Model Registry.

为不同 Provider 的模型 ID 提供统一的语义层（Canonical Model）。
推荐系统、收藏、评分等所有跨 Provider 逻辑都基于 `slug` 主键，
展示时再根据当前 Provider 通过 `aliases` 映射到实际模型 ID。

四类 Provider 的命名差异：

1. 官方厂商（OpenAI / Anthropic / Google）：简洁原生 ID
   - gpt-5, claude-opus-4, gemini-2.5-pro

2. 推理平台（Together / Fireworks / NIM）：保留上游开源模型仓库名
   - meta-llama/Llama-4-Scout-17B-16E-Instruct
   - Qwen/Qwen3-235B-A22B
   - deepseek-ai/DeepSeek-R1

3. 聚合平台（OpenRouter）：自有的 canonical slug
   - openai/gpt-5
   - deepseek/deepseek-r1
   - google/gemini-2.5-pro

4. 本地平台（Ollama，暂未接入）：独立命名
   - llama3.3
   - deepseek-r1:32b
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalModel:
    """跨 Provider 统一的模型定义。

    Attributes:
        slug: 全局唯一主键（如 "deepseek-r1"），推荐/收藏/排序都基于此。
        family: 模型族（如 "DeepSeek R1"），用于按系列分组展示。
        display_name: 用户面向的展示名（如 "DeepSeek R1"）。
        description: 简短描述，可选。
        aliases: provider -> 该 provider 的实际模型 ID。
                 provider 名需与 config.secrets.SUPPORTED_PROVIDERS 一致。
        tags: 标签列表（如 ["reasoning", "open-source"]），用于筛选。
    """

    slug: str
    family: str
    display_name: str
    aliases: dict[str, str] = field(default_factory=dict)
    description: str = ""
    tags: tuple[str, ...] = ()


CANONICAL_REGISTRY: tuple[CanonicalModel, ...] = (
    # ========== OpenAI 官方 ==========
    CanonicalModel(
        slug="gpt-5",
        family="GPT-5",
        display_name="GPT-5",
        description="OpenAI 旗舰通用模型",
        aliases={
            "openai": "gpt-5",
            "openrouter": "openai/gpt-5",
        },
        tags=("flagship", "general"),
    ),
    CanonicalModel(
        slug="gpt-5-mini",
        family="GPT-5",
        display_name="GPT-5 mini",
        description="OpenAI 轻量高效模型",
        aliases={
            "openai": "gpt-5-mini",
            "openrouter": "openai/gpt-5-mini",
        },
        tags=("efficient", "general"),
    ),
    CanonicalModel(
        slug="gpt-4o",
        family="GPT-4o",
        display_name="GPT-4o",
        description="OpenAI 多模态通用模型",
        aliases={
            "openai": "gpt-4o",
            "openrouter": "openai/gpt-4o",
            "together": "gpt-4o",
        },
        tags=("multimodal", "general"),
    ),
    # ========== Anthropic 官方 ==========
    CanonicalModel(
        slug="claude-opus-4",
        family="Claude 4",
        display_name="Claude Opus 4",
        description="Anthropic 顶级推理模型",
        aliases={
            "anthropic": "claude-opus-4-0",
            "openrouter": "anthropic/claude-opus-4",
        },
        tags=("flagship", "reasoning"),
    ),
    CanonicalModel(
        slug="claude-sonnet-4",
        family="Claude 4",
        display_name="Claude Sonnet 4",
        description="Anthropic 均衡模型",
        aliases={
            "anthropic": "claude-sonnet-4-0",
            "openrouter": "anthropic/claude-sonnet-4",
        },
        tags=("balanced", "general"),
    ),
    CanonicalModel(
        slug="claude-haiku-4",
        family="Claude 4",
        display_name="Claude Haiku 4",
        description="Anthropic 轻量模型",
        aliases={
            "anthropic": "claude-haiku-4-0",
            "openrouter": "anthropic/claude-haiku-4",
        },
        tags=("efficient", "general"),
    ),
    # ========== Google 官方 ==========
    CanonicalModel(
        slug="gemini-2.5-pro",
        family="Gemini 2.5",
        display_name="Gemini 2.5 Pro",
        description="Google 顶级推理模型",
        aliases={
            "google": "gemini-2.5-pro",
            "openrouter": "google/gemini-2.5-pro",
        },
        tags=("flagship", "reasoning", "multimodal"),
    ),
    CanonicalModel(
        slug="gemini-2.5-flash",
        family="Gemini 2.5",
        display_name="Gemini 2.5 Flash",
        description="Google 高效模型",
        aliases={
            "google": "gemini-2.5-flash",
            "openrouter": "google/gemini-2.5-flash",
        },
        tags=("efficient", "multimodal"),
    ),
    # ========== DeepSeek ==========
    CanonicalModel(
        slug="deepseek-r1",
        family="DeepSeek R1",
        display_name="DeepSeek R1",
        description="DeepSeek 推理模型，开源高性价比",
        aliases={
            "openrouter": "deepseek/deepseek-r1",
            "together": "deepseek-ai/DeepSeek-R1",
            "nim": "deepseek-ai/deepseek-r1",
        },
        tags=("reasoning", "open-source", "cost-effective"),
    ),
    CanonicalModel(
        slug="deepseek-v3",
        family="DeepSeek V3",
        display_name="DeepSeek V3",
        description="DeepSeek 通用对话模型",
        aliases={
            "openrouter": "deepseek/deepseek-chat",
            "together": "deepseek-ai/DeepSeek-V3",
        },
        tags=("general", "open-source", "cost-effective"),
    ),
    # ========== Meta Llama ==========
    CanonicalModel(
        slug="llama-4-maverick",
        family="Llama 4",
        display_name="Llama 4 Maverick",
        description="Meta Llama 4 旗舰 MoE 模型",
        aliases={
            "together": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "openrouter": "meta-llama/llama-4-maverick",
        },
        tags=("open-source", "multimodal", "moe"),
    ),
    CanonicalModel(
        slug="llama-4-scout",
        family="Llama 4",
        display_name="Llama 4 Scout",
        description="Meta Llama 4 轻量 MoE 模型",
        aliases={
            "together": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
            "openrouter": "meta-llama/llama-4-scout",
        },
        tags=("open-source", "multimodal", "moe"),
    ),
    # ========== Qwen ==========
    CanonicalModel(
        slug="qwen3-235b",
        family="Qwen 3",
        display_name="Qwen3 235B",
        description="阿里 Qwen3 MoE 旗舰模型",
        aliases={
            "together": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "openrouter": "qwen/qwen3-235b-a22b",
        },
        tags=("open-source", "moe", "multilingual"),
    ),
    # ========== 预留 Ollama 别名（暂未接入）==========
    CanonicalModel(
        slug="llama3.3-70b",
        family="Llama 3.3",
        display_name="Llama 3.3 70B",
        description="Meta Llama 3.3 70B（Ollama 命名待接入）",
        aliases={
            "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            # "ollama": "llama3.3:70b",  # 暂不接入
        },
        tags=("open-source", "general"),
    ),
    CanonicalModel(
        slug="qwen3-30b",
        family="Qwen 3",
        display_name="Qwen3 30B",
        description="阿里 Qwen3 30B 稠密模型",
        aliases={
            "together": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            # "ollama": "qwen3:30b",  # 暂不接入
        },
        tags=("open-source", "general"),
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
