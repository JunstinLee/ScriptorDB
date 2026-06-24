from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config.workspace_paths as workspace_paths
import config.workspace_loader as workspace_loader
import config.workspace_registry as workspace_registry_module
import config.settings as settings_module
import server.sessions as sessions_module
from config.workspace_registry import WorkspaceRegistry
from server.app import app
from server.session_file_store import FileSessionStore


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """将注册表 / global config / settings 全部重定向到 tmp_path，避免污染真实 ~ 目录。"""
    config_dir = tmp_path / "config"
    workspaces_root = tmp_path / "workspaces"
    config_dir.mkdir(parents=True, exist_ok=True)
    workspaces_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workspace_paths, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(workspace_paths, "DEFAULT_WORKSPACES_DIR", workspaces_root)
    monkeypatch.setattr(workspace_paths, "REGISTRY_FILE", config_dir / "workspaces.json")
    monkeypatch.setattr(workspace_paths, "LEGACY_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(workspace_paths, "LEGACY_SESSIONS_DIR", config_dir / "sessions")
    monkeypatch.setattr(workspace_paths, "LEGACY_SESSIONS_FILE", config_dir / "sessions.json")
    monkeypatch.setattr(
        workspace_paths, "LEGACY_SESSIONS_BACKUP_FILE", config_dir / "sessions.json.bak"
    )

    import config.workspace as workspace_module
    monkeypatch.setattr(workspace_module, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(workspace_module, "DEFAULT_WORKSPACES_DIR", workspaces_root)
    monkeypatch.setattr(workspace_module, "REGISTRY_FILE", config_dir / "workspaces.json")

    monkeypatch.setattr(workspace_registry_module, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(workspace_registry_module, "REGISTRY_FILE", config_dir / "workspaces.json")
    monkeypatch.setattr(workspace_registry_module, "DEFAULT_WORKSPACES_DIR", workspaces_root)

    monkeypatch.setattr(workspace_loader, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(workspace_loader, "REGISTRY_FILE", config_dir / "workspaces.json")
    monkeypatch.setattr(workspace_loader, "LEGACY_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(workspace_loader, "LEGACY_SESSIONS_DIR", config_dir / "sessions")
    monkeypatch.setattr(workspace_loader, "LEGACY_SESSIONS_FILE", config_dir / "sessions.json")
    monkeypatch.setattr(
        workspace_loader, "LEGACY_SESSIONS_BACKUP_FILE", config_dir / "sessions.json.bak"
    )

    fresh = settings_module.Settings()
    fresh.workspace_id = None
    fresh.workspace_name = None
    fresh.workspace_path = None
    fresh.db_url = ""
    fresh.llm_provider = "openai"
    fresh.llm_model = None
    fresh.default_models = {}
    fresh.auto_restore_sessions = True
    monkeypatch.setattr(settings_module, "settings", fresh)

    sessions_module.session_store = None

    from config.workspace_paths import REGISTRY_FILE as _RF
    if _RF.exists():
        _RF.unlink()

    return tmp_path


@pytest.fixture
def client(workspace_env):
    return TestClient(app)


def _create_workspace(path: Path, name: str) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    rec = WorkspaceRegistry().create(path, name=name)
    return {"id": rec.id, "name": rec.name, "path": str(rec.path)}


def _file_store() -> FileSessionStore:
    import server.sessions as sm
    assert sm.session_store is not None
    return sm.session_store  # type: ignore[return-value]


def test_activate_workspace_swaps_session_store(workspace_env, client):
    """切换工作区时，server.sessions.session_store 必须指向新工作区。"""
    import server.sessions as sm

    ws_a_path = workspace_env / "wsA"
    ws_b_path = workspace_env / "wsB"
    ws_a = _create_workspace(ws_a_path, "wsA")
    ws_b = _create_workspace(ws_b_path, "wsB")

    resp = client.post(f"/api/workspaces/{ws_a['id']}/activate")
    assert resp.status_code == 200, resp.text
    store_a = _file_store()
    assert str(ws_a_path) in str(store_a._storage_dir)

    create_resp = client.post("/api/sessions")
    assert create_resp.status_code == 200, create_resp.text
    sid_a = create_resp.json()["session_id"]
    assert sid_a in store_a._sessions

    list_a = client.get("/api/sessions").json()
    assert [s["session_id"] for s in list_a["sessions"]] == [sid_a]

    resp = client.post(f"/api/workspaces/{ws_b['id']}/activate")
    assert resp.status_code == 200, resp.text

    store_b = _file_store()
    assert id(store_b) != id(store_a), (
        "session_store 没有被替换：切换工作区后仍指向旧对象。"
    )
    assert str(ws_b_path) in str(store_b._storage_dir)
    assert sid_a not in store_b._sessions

    list_b = client.get("/api/sessions").json()
    assert list_b["sessions"] == []

    resp = client.post(f"/api/workspaces/{ws_a['id']}/activate")
    assert resp.status_code == 200, resp.text
    store_a_again = _file_store()
    assert id(store_a_again) != id(store_b)
    assert sid_a in store_a_again._sessions
    list_a_again = client.get("/api/sessions").json()
    assert [s["session_id"] for s in list_a_again["sessions"]] == [sid_a]


def test_get_session_after_workspace_switch_uses_correct_store(workspace_env, client):
    """切到工作区 B 后，取属于 A 的 session id 应得 404。"""
    ws_a_path = workspace_env / "wsA"
    ws_b_path = workspace_env / "wsB"
    ws_a = _create_workspace(ws_a_path, "wsA")
    ws_b = _create_workspace(ws_b_path, "wsB")

    client.post(f"/api/workspaces/{ws_a['id']}/activate")
    sid = client.post("/api/sessions").json()["session_id"]

    client.post(f"/api/workspaces/{ws_b['id']}/activate")

    resp = client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 404
    assert sid not in _file_store()._sessions
