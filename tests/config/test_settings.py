from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import config.global_settings as gs_module
import config.secrets as secrets
import api.dependencies as dependencies
from config.app_config import AppConfig
from api.app import app


class FakeKeyring:
    def __init__(self):
        self.store: dict[str, dict[str, str]] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store.setdefault(service, {})[username] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get(service, {}).get(username)

    def delete_password(self, service: str, username: str) -> None:
        self.store.get(service, {}).pop(username, None)


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    # 重定向全局配置持久化到 tmp_path,避免污染真实 ~/.config/scriptordb
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(gs_module, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(gs_module, "GLOBAL_SETTINGS_FILE", config_dir / "global_settings.json")

    # API key 读写走内存 keyring
    monkeypatch.setattr(secrets, "keyring", FakeKeyring())

    # 带 workspace 的配置单例(get_config / require_workspace 均读取它)
    ws_path = tmp_path / "ws"
    ws_path.mkdir(parents=True, exist_ok=True)
    fresh = AppConfig()
    fresh.workspace_id = "ws-test"
    fresh.workspace_name = "test-ws"
    fresh.workspace_path = ws_path
    fresh.llm_provider = "deepseek"
    fresh.llm_model = None
    fresh.default_models = {}
    fresh.auto_restore_sessions = True
    fresh.browser_enabled = False
    monkeypatch.setattr(dependencies, "settings", fresh)

    return TestClient(app)


def test_get_settings_returns_supported_providers(client: TestClient):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "deepseek"
    assert data["auto_restore_sessions"] is True
    assert any(p["name"] == "deepseek" for p in data["providers"])
    assert any(p["name"] == "openrouter" for p in data["providers"])
    assert data["providers_with_keys"] == []


def test_update_settings_changes_provider(client: TestClient):
    resp = client.post("/api/settings", json={"llm_provider": "openrouter"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "openrouter"


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


def test_update_settings_persists_to_global_file(client: TestClient, tmp_path: Path):
    client.post("/api/settings", json={"llm_provider": "openrouter"})
    expected_file = tmp_path / "config" / "global_settings.json"
    assert expected_file.exists()
    raw = json.loads(expected_file.read_text())
    assert raw["llm_provider"] == "openrouter"


def test_set_api_key_persists_to_keyring(client: TestClient):
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "deepseek", "api_key": "sk-test-1234"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    settings_resp = client.get("/api/settings")
    assert "deepseek" in settings_resp.json()["providers_with_keys"]


def test_set_api_key_rejects_empty(client: TestClient):
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "deepseek", "api_key": "   "},
    )
    assert resp.status_code == 400


def test_delete_api_key(client: TestClient):
    client.post(
        "/api/settings/api-key",
        json={"provider": "deepseek", "api_key": "sk-test"},
    )
    resp = client.delete("/api/settings/api-key/deepseek")
    assert resp.status_code == 200
    assert "deepseek" not in client.get("/api/settings").json()["providers_with_keys"]


def test_test_api_key_success(client: TestClient):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None: ...

    with patch("services.api_key_service.httpx.get", return_value=FakeResp()):
        resp = client.post(
            "/api/settings/api-key/test",
            json={"provider": "deepseek", "api_key": "sk-test"},
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

    with patch("services.api_key_service.httpx.get", return_value=FakeResp()):
        resp = client.post(
            "/api/settings/api-key/test",
            json={"provider": "deepseek", "api_key": "sk-bad"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
