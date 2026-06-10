from __future__ import annotations

from config import models


def test_parse_openai_style():
    data = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4.1"}, {"id": "gpt-4o"}]}
    result = models._parse_models(data)
    assert result == ["gpt-4.1", "gpt-4o"]


def test_parse_anthropic_style():
    data = {"models": [{"id": "claude-3-opus"}, {"name": "claude-3-sonnet"}]}
    result = models._parse_models(data)
    assert "claude-3-opus" in result
    assert "claude-3-sonnet" in result


def test_parse_empty():
    assert models._parse_models({}) == []
    assert models._parse_models({"data": []}) == []
    assert models._parse_models({"models": []}) == []


def test_parse_skips_invalid_entries():
    data = {"data": [{"id": "good"}, "not-a-dict", {}, {"id": None}, {"id": "good"}]}
    result = models._parse_models(data)
    assert result == ["good"]


def test_resolve_model_with_prefix():
    assert models.resolve_model("openai", "openai:gpt-4o") == "openai:gpt-4o"


def test_resolve_model_bare_name():
    assert models.resolve_model("openai", "gpt-4o") == "openai:gpt-4o"


def test_resolve_model_with_other_provider_prefix():
    assert models.resolve_model("openai", "anthropic:claude-3") == "anthropic:claude-3"


def test_resolve_model_unsupported_provider():
    import pytest

    with pytest.raises(ValueError):
        models.resolve_model("not-a-provider", None)


def test_fuzzy_match_exact(monkeypatch):
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: ["gpt-4o", "gpt-4.1"]
    )
    assert models.fuzzy_match_model("openai", "gpt-4o") == "gpt-4o"


def test_fuzzy_match_substring_unique(monkeypatch):
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: ["gpt-4o", "gpt-4.1"]
    )
    assert models.fuzzy_match_model("openai", "4.1") == "gpt-4.1"


def test_fuzzy_match_no_match(monkeypatch):
    monkeypatch.setattr(
        models, "list_available_models", lambda provider, use_cache=True: ["gpt-4o", "gpt-4.1"]
    )
    assert models.fuzzy_match_model("openai", "claude") is None
