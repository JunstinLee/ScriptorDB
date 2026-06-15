from __future__ import annotations

from config import models
from config.canonical_models import (
    CANONICAL_REGISTRY,
    _load_registry,
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


import json
import pytest


def make_json_file(tmp_path, data):
    p = tmp_path / "models.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_loader_valid_json(tmp_path):
    p = make_json_file(tmp_path, [
        {"slug": "test-model", "display_name": "Test Model", "aliases": {"openai": "test-model"}},
    ])
    registry = _load_registry(p)
    assert len(registry) == 1
    assert registry[0].slug == "test-model"
    assert registry[0].display_name == "Test Model"
    assert registry[0].aliases == {"openai": "test-model"}


def test_loader_empty_array(tmp_path):
    p = make_json_file(tmp_path, [])
    registry = _load_registry(p)
    assert registry == ()


def test_loader_missing_file(tmp_path):
    with pytest.raises(ValueError, match="Failed to read"):
        _load_registry(tmp_path / "nonexistent.json")


def test_loader_invalid_json(tmp_path):
    p = tmp_path / "models.json"
    p.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        _load_registry(p)


def test_loader_not_a_list(tmp_path):
    p = make_json_file(tmp_path, {"slug": "x"})
    with pytest.raises(ValueError, match="must contain a JSON array"):
        _load_registry(p)


def test_loader_entry_not_a_dict(tmp_path):
    p = make_json_file(tmp_path, ["not-a-dict"])
    with pytest.raises(ValueError, match="must be an object"):
        _load_registry(p)


def test_loader_missing_slug(tmp_path):
    p = make_json_file(tmp_path, [{"display_name": "X", "aliases": {}}])
    with pytest.raises(ValueError, match="missing or invalid 'slug'"):
        _load_registry(p)


def test_loader_empty_slug(tmp_path):
    p = make_json_file(tmp_path, [{"slug": "", "display_name": "X", "aliases": {}}])
    with pytest.raises(ValueError, match="missing or invalid 'slug'"):
        _load_registry(p)


def test_loader_missing_display_name(tmp_path):
    p = make_json_file(tmp_path, [{"slug": "x", "aliases": {}}])
    with pytest.raises(ValueError, match="missing or invalid 'display_name'"):
        _load_registry(p)


def test_loader_missing_aliases(tmp_path):
    p = make_json_file(tmp_path, [{"slug": "x", "display_name": "X"}])
    with pytest.raises(ValueError, match="missing or invalid 'aliases'"):
        _load_registry(p)


def test_loader_invalid_aliases_type(tmp_path):
    p = make_json_file(tmp_path, [{"slug": "x", "display_name": "X", "aliases": "not-dict"}])
    with pytest.raises(ValueError, match="missing or invalid 'aliases'"):
        _load_registry(p)


def test_loader_duplicate_slug(tmp_path):
    p = make_json_file(tmp_path, [
        {"slug": "dup", "display_name": "A", "aliases": {}},
        {"slug": "dup", "display_name": "B", "aliases": {}},
    ])
    with pytest.raises(ValueError, match="Duplicate slug 'dup'"):
        _load_registry(p)


def test_loader_invalid_provider_key(tmp_path):
    p = make_json_file(tmp_path, [
        {"slug": "x", "display_name": "X", "aliases": {"": "alias"}},
    ])
    with pytest.raises(ValueError, match="invalid provider key"):
        _load_registry(p)


def test_loader_invalid_alias_value(tmp_path):
    p = make_json_file(tmp_path, [
        {"slug": "x", "display_name": "X", "aliases": {"openai": ""}},
    ])
    with pytest.raises(ValueError, match="invalid alias for provider 'openai'"):
        _load_registry(p)


def test_loader_preserves_order(tmp_path):
    p = make_json_file(tmp_path, [
        {"slug": "first", "display_name": "F", "aliases": {}},
        {"slug": "second", "display_name": "S", "aliases": {}},
        {"slug": "third", "display_name": "T", "aliases": {}},
    ])
    registry = _load_registry(p)
    assert [m.slug for m in registry] == ["first", "second", "third"]


def test_json_file_matches_registry():
    from pathlib import Path
    json_path = Path(__file__).parent.parent / "config" / "recommended_models.json"
    registry = _load_registry(json_path)
    assert len(registry) == len(CANONICAL_REGISTRY)
    for m_json, m_code in zip(registry, CANONICAL_REGISTRY):
        assert m_json.slug == m_code.slug
        assert m_json.display_name == m_code.display_name
        assert m_json.aliases == m_code.aliases
