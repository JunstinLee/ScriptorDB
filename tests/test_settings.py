from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import config.settings as settings_module
from server.app import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(settings_module, "_CONFIG_FILE", config_file)
    from config.settings import Settings

    fresh = Settings()
    fresh.auto_restore_sessions = True
    fresh.default_models = {}
    fresh.llm_provider = "openai"
    fresh.llm_model = None
    monkeypatch.setattr(settings_module, "settings", fresh)
    fake_keys: dict[str, str] = {}
    monkeypatch.setattr(
        "server.app.get_api_key",
        lambda provider: fake_keys.get(provider),
    )
    monkeypatch.setattr(
        "server.app.save_api_key", lambda provider, key: fake_keys.__setitem__(provider, key)
    )
    monkeypatch.setattr(
        "server.app.delete_api_key", lambda provider: fake_keys.pop(provider, None)
    )
    return TestClient(app)


def test_get_settings_returns_supported_providers(client: TestClient):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "openai"
    assert data["auto_restore_sessions"] is True
    assert any(p["name"] == "openai" for p in data["providers"])
    assert data["providers_with_keys"] == []


def test_update_settings_changes_provider(client: TestClient):
    resp = client.post(
        "/api/settings",
        json={"llm_provider": "groq"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "groq"


def test_update_settings_rejects_unknown_provider(client: TestClient):
    resp = client.post(
        "/api/settings",
        json={"llm_provider": "not-a-real-provider"},
    )
    assert resp.status_code == 400


def test_update_settings_toggles_auto_restore(client: TestClient):
    resp = client.post(
        "/api/settings",
        json={"auto_restore_sessions": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_restore_sessions"] is False


def test_update_settings_persists_to_config_file(client: TestClient, tmp_path: Path):
    client.post("/api/settings", json={"llm_provider": "anthropic"})
    expected_file = tmp_path / "config.json"
    assert expected_file.exists()
    raw = json.loads(expected_file.read_text())
    assert raw["llm_provider"] == "anthropic"


def test_set_api_key_persists_to_keyring(client: TestClient):
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "sk-test-1234"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    settings_resp = client.get("/api/settings")
    assert "openai" in settings_resp.json()["providers_with_keys"]


def test_set_api_key_rejects_empty(client: TestClient):
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "   "},
    )
    assert resp.status_code == 400


def test_delete_api_key(client: TestClient):
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "sk-test"},
    )
    resp = client.delete("/api/settings/api-key/openai")
    assert resp.status_code == 200
    assert "openai" not in client.get("/api/settings").json()["providers_with_keys"]


def test_test_api_key_success(client: TestClient):
    class FakeResp:
        status_code = 200
        def raise_for_status(self) -> None: ...

    def fake_get(url, headers=None, timeout=None):
        return FakeResp()

    with patch("server.app.httpx.get", side_effect=fake_get):
        resp = client.post(
            "/api/settings/api-key/test",
            json={"provider": "openai", "api_key": "sk-test"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_test_api_key_failure(client: TestClient):
    class FakeResp:
        status_code = 401
        def raise_for_status(self):
            import httpx
            req = httpx.Request("GET", "http://example.com")
            raise httpx.HTTPStatusError("401", request=req, response=httpx.Response(401))

    def fake_get(url, headers=None, timeout=None):
        return FakeResp()

    with patch("server.app.httpx.get", side_effect=fake_get):
        resp = client.post(
            "/api/settings/api-key/test",
            json={"provider": "openai", "api_key": "sk-bad"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
