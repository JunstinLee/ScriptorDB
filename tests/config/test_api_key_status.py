from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

import api.dependencies as dependencies
from api.app import app
from config.app_config import AppConfig
from config.secrets import SUPPORTED_PROVIDERS
from services import api_key_service
from services.api_key_service import (
    check_api_key_status,
    clear_status_cache,
    probe_key,
)


class _OkResp:
    status_code = 200

    def raise_for_status(self) -> None: ...


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test/models")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


@pytest.fixture(autouse=True)
def _clear_status_cache():
    """缓存以 workspace+provider 为键，跨用例会互相污染。"""
    clear_status_cache()
    yield
    clear_status_cache()


@pytest.fixture
def client(tmp_path: Path, monkeypatch, fake_keyring):
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


def _save_key(client: TestClient, provider: str = "deepseek") -> None:
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": provider, "api_key": "sk-test"},
    )
    assert resp.status_code == 200


def test_status_is_missing_when_no_key_stored(client: TestClient):
    resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "deepseek"
    assert data["status"] == "missing"
    assert data["error"] is None
    assert data["checked_at"]


def test_status_is_valid_when_provider_accepts_key(client: TestClient):
    _save_key(client)
    with patch("services.api_key_service.httpx.get", return_value=_OkResp()):
        resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "valid"


def test_status_is_invalid_when_provider_rejects_key(client: TestClient):
    _save_key(client)
    with patch(
        "services.api_key_service.httpx.get", side_effect=_status_error(401)
    ):
        resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "invalid"
    assert "401" in data["error"]


def test_status_is_unknown_when_provider_unreachable(client: TestClient):
    _save_key(client)
    with patch(
        "services.api_key_service.httpx.get",
        side_effect=httpx.ConnectError("dns lookup failed"),
    ):
        resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unknown"
    assert "dns lookup failed" in data["error"]


def test_status_returns_200_even_when_provider_errors(client: TestClient):
    _save_key(client)
    with patch(
        "services.api_key_service.httpx.get", side_effect=_status_error(503)
    ):
        resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unknown"


def test_status_is_no_workspace_without_active_workspace(
    client: TestClient, monkeypatch
):
    fresh = AppConfig()
    fresh.workspace_id = None
    fresh.llm_provider = "deepseek"
    monkeypatch.setattr(dependencies, "settings", fresh)

    with patch("services.api_key_service.httpx.get", return_value=_OkResp()) as probe:
        resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_workspace"
    assert probe.call_count == 0


def test_status_accepts_explicit_provider(client: TestClient):
    resp = client.get("/api/settings/api-key/status?provider=openrouter")
    assert resp.status_code == 200
    assert resp.json()["provider"] == "openrouter"


def test_status_rejects_unsupported_provider(client: TestClient):
    resp = client.get("/api/settings/api-key/status?provider=nope")
    assert resp.status_code == 400


def test_status_is_cached_until_refreshed(client: TestClient):
    _save_key(client)
    with patch(
        "services.api_key_service.httpx.get", side_effect=_status_error(401)
    ):
        assert client.get("/api/settings/api-key/status").json()["status"] == "invalid"

    # 缓存期内即使 provider 已恢复，也不重新探测
    with patch("services.api_key_service.httpx.get", return_value=_OkResp()) as probe:
        assert client.get("/api/settings/api-key/status").json()["status"] == "invalid"
        assert probe.call_count == 0
        refreshed = client.get("/api/settings/api-key/status?refresh=true")
    assert refreshed.json()["status"] == "valid"


def test_saving_a_key_clears_the_cached_status(client: TestClient):
    with patch(
        "services.api_key_service.httpx.get", side_effect=_status_error(401)
    ):
        assert client.get("/api/settings/api-key/status").json()["status"] == "missing"

    _save_key(client)
    with patch("services.api_key_service.httpx.get", return_value=_OkResp()):
        resp = client.get("/api/settings/api-key/status")
    assert resp.json()["status"] == "valid"


def test_probe_key_classifies_auth_failures_as_invalid():
    cfg = SUPPORTED_PROVIDERS["deepseek"]
    for code in (401, 403):
        with patch(
            "services.api_key_service.httpx.get", side_effect=_status_error(code)
        ):
            assert probe_key(cfg, "sk-test")[0] == "invalid"


def test_probe_key_classifies_transport_failures_as_unknown():
    cfg = SUPPORTED_PROVIDERS["deepseek"]
    with patch(
        "services.api_key_service.httpx.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        assert probe_key(cfg, "sk-test")[0] == "unknown"


def test_probe_key_accepts_a_healthy_provider():
    cfg = SUPPORTED_PROVIDERS["deepseek"]
    with patch("services.api_key_service.httpx.get", return_value=_OkResp()):
        assert probe_key(cfg, "sk-test") == ("valid", None)


def test_test_key_keeps_its_boolean_contract():
    cfg = SUPPORTED_PROVIDERS["deepseek"]
    with patch("services.api_key_service.httpx.get", return_value=_OkResp()):
        assert api_key_service.test_key(cfg, "sk-test") == (True, None)
    with patch("services.api_key_service.httpx.get", side_effect=_status_error(403)):
        ok, error = api_key_service.test_key(cfg, "sk-test")
    assert ok is False
    assert error


def test_check_status_rejects_unsupported_provider():
    with pytest.raises(ValueError):
        check_api_key_status("nope", "ws-test")
