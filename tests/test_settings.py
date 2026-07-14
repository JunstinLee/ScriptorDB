from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from config.workspace_paths import GLOBAL_SETTINGS_FILE, GLOBAL_CONFIG_DIR
from server.app import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    settings_file = tmp_path / "global_settings.json"
    monkeypatch.setattr(
        "config.workspace_paths.GLOBAL_SETTINGS_FILE", settings_file
    )
    monkeypatch.setattr(
        "config.workspace_paths.GLOBAL_CONFIG_DIR", tmp_path
    )

    settings.workspace_id = "test-ws-id"
    settings.workspace_name = "test-ws"
    settings.workspace_path = tmp_path
    settings.db_url = "sqlite:///:memory:"
    settings.llm_provider = "openai"
    settings.llm_model = None
    settings.default_models = {}
    settings.auto_restore_sessions = True

    fake_keys: dict[str, str] = {}
    monkeypatch.setattr(
        "config.secrets.get_api_key",
        lambda provider, workspace_id=None: fake_keys.get(provider),
    )
    monkeypatch.setattr(
        "config.secrets.save_api_key",
        lambda provider, key, workspace_id=None: fake_keys.__setitem__(provider, key),
    )
    monkeypatch.setattr(
        "config.secrets.delete_api_key",
        lambda provider, workspace_id=None: fake_keys.pop(provider, None),
    )

    yield TestClient(app)

    settings.clear()


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
    assert GLOBAL_SETTINGS_FILE.exists()
    raw = __import__("json").loads(GLOBAL_SETTINGS_FILE.read_text())
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

    with patch("server.routes.api_keys.httpx.get", side_effect=fake_get):
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

    with patch("server.routes.api_keys.httpx.get", side_effect=fake_get):
        resp = client.post(
            "/api/settings/api-key/test",
            json={"provider": "openai", "api_key": "sk-bad"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
