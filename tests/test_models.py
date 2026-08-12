from __future__ import annotations

import pytest

from config import models
from config.models import resolver as resolver_module
from config.models.client import _parse_models


def test_parse_openai_style():
    data = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4.1"}, {"id": "gpt-4o"}]}
    result = _parse_models(data)
    assert result == ["gpt-4.1", "gpt-4o"]


def test_parse_anthropic_style():
    data = {"models": [{"id": "claude-3-opus"}, {"name": "claude-3-sonnet"}]}
    result = _parse_models(data)
    assert "claude-3-opus" in result
    assert "claude-3-sonnet" in result


def test_parse_empty():
    assert _parse_models({}) == []
    assert _parse_models({"data": []}) == []
    assert _parse_models({"models": []}) == []


def test_parse_skips_invalid_entries():
    data = {"data": [{"id": "good"}, "not-a-dict", {}, {"id": None}, {"id": "good"}]}
    result = _parse_models(data)
    assert result == ["good"]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("openai:gpt-4o", "openai:gpt-4o"),
        ("gpt-4o", "openai:gpt-4o"),
        ("anthropic:claude-3", "anthropic:claude-3"),
    ],
)
def test_resolve_model(model, expected):
    assert models.resolve_model("deepseek", model) == expected


def test_resolve_model_unsupported_provider():
    with pytest.raises(ValueError):
        models.resolve_model("not-a-provider", None)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("gpt-4o", "gpt-4o"),
        ("4.1", "gpt-4.1"),
        ("claude", None),
    ],
)
def test_fuzzy_match(monkeypatch, query, expected):
    monkeypatch.setattr(
        resolver_module, "list_available_models", lambda provider, use_cache=True, **kwargs: ["gpt-4o", "gpt-4.1"]
    )
    assert models.fuzzy_match_model("openrouter", query) == expected


def test_filter_chat_models_excludes_keywords():
    raw = [
        "gpt-4o",
        "text-embedding-3-large",
        "tts-1",
        "whisper-1",
        "claude-sonnet-4",
        "text-moderation-stable",
        "rerank-english-v3",
        "audio-transcriber",
        "speech-to-text-v1",
    ]
    result = models.filter_chat_models(raw)
    assert result == ["gpt-4o", "claude-sonnet-4"]


def test_filter_chat_models_empty():
    assert models.filter_chat_models([]) == []

