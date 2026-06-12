from __future__ import annotations

from config import models
from config.canonical_models import (
    CANONICAL_REGISTRY,
    get_canonical_by_slug,
    get_canonical_for_provider,
    get_canonical_for_provider_model,
)


def test_canonical_registry_is_not_empty():
    assert len(CANONICAL_REGISTRY) > 0


def test_canonical_slugs_are_unique():
    slugs = [m.slug for m in CANONICAL_REGISTRY]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"


def test_canonical_aliases_reference_known_providers():
    from config.secrets import SUPPORTED_PROVIDERS

    known = set(SUPPORTED_PROVIDERS.keys()) | {"official"}
    for m in CANONICAL_REGISTRY:
        for provider in m.aliases:
            assert provider in known, (
                f"Unknown provider '{provider}' in alias of '{m.slug}'"
            )


def test_get_canonical_by_slug_hit():
    m = get_canonical_by_slug("deepseek-r1")
    assert m is not None
    assert m.display_name == "DeepSeek R1"
    assert m.family == "DeepSeek R1"


def test_get_canonical_by_slug_miss():
    assert get_canonical_by_slug("non-existent-slug") is None


def test_get_canonical_for_provider_openrouter():
    items = get_canonical_for_provider("openrouter")
    slugs = [m.slug for m in items]
    assert "gpt-5" in slugs
    assert "deepseek-r1" in slugs
    assert "claude-opus-4" in slugs


def test_get_canonical_for_provider_together():
    items = get_canonical_for_provider("together")
    slugs = [m.slug for m in items]
    assert "deepseek-r1" in slugs
    assert "llama-4-maverick" in slugs
    for m in items:
        if m.slug == "llama-4-maverick":
            assert m.aliases["together"].startswith("meta-llama/")


def test_get_canonical_for_provider_official():
    items = get_canonical_for_provider("openai")
    slugs = [m.slug for m in items]
    assert "gpt-5" in slugs
    assert "gpt-4o" in slugs


def test_reverse_resolve_exact():
    m = get_canonical_for_provider_model("openrouter", "openai/gpt-5")
    assert m is not None
    assert m.slug == "gpt-5"


def test_reverse_resolve_together_hf_style():
    m = get_canonical_for_provider_model(
        "together", "deepseek-ai/DeepSeek-R1"
    )
    assert m is not None
    assert m.slug == "deepseek-r1"


def test_reverse_resolve_official():
    m = get_canonical_for_provider_model("openai", "gpt-5")
    assert m is not None
    assert m.slug == "gpt-5"


def test_reverse_resolve_unknown():
    m = get_canonical_for_provider_model("openrouter", "totally/unknown-model")
    assert m is None


def test_reverse_resolve_empty():
    assert get_canonical_for_provider_model("openai", "") is None


def test_models_resolve_canonical_slug_known():
    assert models.resolve_canonical_slug("openrouter", "openai/gpt-5") == "gpt-5"
    assert models.resolve_canonical_slug("together", "deepseek-ai/DeepSeek-R1") == "deepseek-r1"
    assert models.resolve_canonical_slug("openai", "gpt-5") == "gpt-5"


def test_models_resolve_canonical_slug_unknown():
    assert models.resolve_canonical_slug("openai", "no-such-model") is None


def test_list_canonical_models_no_provider():
    items = models.list_canonical_models()
    assert len(items) == len(CANONICAL_REGISTRY)
    for item in items:
        assert "available_providers" in item
        assert "provider_specific_id" not in item


def test_list_canonical_models_with_provider():
    items = models.list_canonical_models("openrouter")
    assert all(item["provider_specific_id"] is not None for item in items)
    assert all(item.get("available_providers") is None for item in items)
    deepseek = next(i for i in items if i["slug"] == "deepseek-r1")
    assert deepseek["provider_specific_id"] == "deepseek/deepseek-r1"


def test_get_recommended_models_uses_canonical(monkeypatch):
    fake_models = [
        "openai/gpt-5",
        "openai/gpt-5-mini",
        "anthropic/claude-opus-4",
        "deepseek/deepseek-r1",
        "random/model",
        "text-embedding-3-small",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("openrouter")
    assert "openai/gpt-5" in result
    assert "deepseek/deepseek-r1" in result
    assert "random/model" not in result


def test_get_recommended_models_together_hf_style(monkeypatch):
    fake_models = [
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "deepseek-ai/DeepSeek-R1",
        "totally-unrelated/foo",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("together")
    assert "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8" in result
    assert "deepseek-ai/DeepSeek-R1" in result
    assert "totally-unrelated/foo" not in result


def test_get_recommended_models_deduplicates(monkeypatch):
    fake_models = [
        "openai/gpt-5",
        "openai/gpt-5",
        "deepseek/deepseek-r1",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("openrouter")
    assert result.count("openai/gpt-5") == 1


def test_get_recommended_models_no_match_returns_empty(monkeypatch):
    fake_models = ["totally/unrelated", "another/random"]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("openrouter")
    assert result == []


def test_get_recommended_models_handles_listing_error(monkeypatch):
    def fake_listing(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(models, "list_available_models", fake_listing)
    result = models.get_recommended_models("openrouter")
    assert result == []


def test_canonical_models_have_required_fields():
    for m in CANONICAL_REGISTRY:
        assert m.slug
        assert m.family
        assert m.display_name
        assert isinstance(m.aliases, dict)
        assert isinstance(m.tags, tuple)


def test_canonical_aliases_are_non_empty_strings():
    for m in CANONICAL_REGISTRY:
        for provider, alias in m.aliases.items():
            assert isinstance(alias, str) and alias, (
                f"Empty alias for {m.slug} on {provider}"
            )
