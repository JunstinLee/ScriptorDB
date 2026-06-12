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
    m = get_canonical_by_slug("deepseek-v4-pro")
    assert m is not None
    assert m.display_name == "DeepSeek V4 Pro"


def test_get_canonical_by_slug_miss():
    assert get_canonical_by_slug("non-existent-slug") is None


def test_get_canonical_for_provider_openrouter():
    items = get_canonical_for_provider("openrouter")
    slugs = [m.slug for m in items]
    assert "gpt-5.5" in slugs
    assert "deepseek-v4-pro" in slugs
    assert "claude-opus-4-8" in slugs


def test_get_canonical_for_provider_together():
    items = get_canonical_for_provider("together")
    slugs = [m.slug for m in items]
    assert "deepseek-v4-pro" in slugs
    assert "minimax-m3" in slugs


def test_get_canonical_for_provider_official():
    items = get_canonical_for_provider("openai")
    slugs = [m.slug for m in items]
    assert "gpt-5.5" in slugs
    assert "gpt-5.5-pro" in slugs


def test_get_canonical_for_provider_nim():
    items = get_canonical_for_provider("nim")
    slugs = [m.slug for m in items]
    assert "deepseek-v4-pro" in slugs
    assert "kimi-2.6" in slugs
    assert "minimax-2.7" in slugs
    assert "glm-5" in slugs


def test_reverse_resolve_exact():
    m = get_canonical_for_provider_model("openrouter", "gpt-5.5")
    assert m is not None
    assert m.slug == "gpt-5.5"


def test_reverse_resolve_together_hf_style():
    m = get_canonical_for_provider_model(
        "together", "deepseek-v4-pro"
    )
    assert m is not None
    assert m.slug == "deepseek-v4-pro"


def test_reverse_resolve_official():
    m = get_canonical_for_provider_model("openai", "gpt-5.5")
    assert m is not None
    assert m.slug == "gpt-5.5"


def test_reverse_resolve_unknown():
    m = get_canonical_for_provider_model("openrouter", "totally/unknown-model")
    assert m is None


def test_reverse_resolve_empty():
    assert get_canonical_for_provider_model("openai", "") is None


def test_models_resolve_canonical_slug_known():
    assert models.resolve_canonical_slug("openrouter", "gpt-5.5") == "gpt-5.5"
    assert models.resolve_canonical_slug("together", "deepseek-v4-pro") == "deepseek-v4-pro"
    assert models.resolve_canonical_slug("openai", "gpt-5.5") == "gpt-5.5"


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
    deepseek = next(i for i in items if i["slug"] == "deepseek-v4-pro")
    assert deepseek["provider_specific_id"] == "deepseek-v4-pro"


def test_get_recommended_models_uses_canonical(monkeypatch):
    fake_models = [
        "gpt-5.5",
        "gpt-5.5-pro",
        "claude-opus-4-8",
        "deepseek-v4-pro",
        "random/model",
        "text-embedding-3-small",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("openrouter")
    assert "gpt-5.5" in result
    assert "deepseek-v4-pro" in result
    assert "random/model" not in result


def test_get_recommended_models_together_hf_style(monkeypatch):
    fake_models = [
        "deepseek-v4-pro",
        "kimi-2.6",
        "minimax-m3",
        "totally-unrelated/foo",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("together")
    assert "deepseek-v4-pro" in result
    assert "kimi-2.6" in result
    assert "totally-unrelated/foo" not in result


def test_get_recommended_models_deduplicates(monkeypatch):
    fake_models = [
        "gpt-5.5",
        "gpt-5.5",
        "deepseek-v4-pro",
    ]
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: fake_models
    )

    result = models.get_recommended_models("openrouter")
    assert result.count("gpt-5.5") == 1


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
        assert m.display_name
        assert isinstance(m.aliases, dict)


def test_canonical_aliases_are_non_empty_strings():
    for m in CANONICAL_REGISTRY:
        for provider, alias in m.aliases.items():
            assert isinstance(alias, str) and alias, (
                f"Empty alias for {m.slug} on {provider}"
            )
