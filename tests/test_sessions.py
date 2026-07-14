from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from server.schemas import MessageItem, SessionCreateResponse
from server.sessions import (
    _LEGACY_BACKUP_FILE,
    _LEGACY_SESSIONS_FILE,
    Session,
    SessionStore,
)


def _storage(tmp_path: Path) -> Path:
    return tmp_path / "sessions"


def test_session_store_create_persists(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    assert s.session_id in store._sessions
    file_path = storage / store._session_relpath(s)
    assert file_path.exists()
    assert (storage / "_index.json").exists()


def test_session_store_save_load_roundtrip(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    s.add_user_message("hello")
    s.add_assistant_message("hi there")
    store.save()

    store2 = SessionStore(storage_path=storage)
    loaded = store2.get(s.session_id)
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert loaded.messages[0].role == "user"
    assert loaded.messages[0].content == "hello"
    assert loaded.messages[1].role == "assistant"
    assert loaded.messages[1].content == "hi there"


def test_session_store_delete_persists(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    file_path = storage / store._session_relpath(s)
    assert file_path.exists()
    assert store.delete(s.session_id) is True
    assert not file_path.exists()
    store2 = SessionStore(storage_path=storage)
    assert store2.get(s.session_id) is None


def test_session_store_no_ttl_keeps_old_sessions(tmp_path: Path):
    storage = _storage(tmp_path)
    payload = {
        "version": 1,
        "index": {
            "old001": {
                "path": "2024/01/old001.json",
                "created_at": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                "last_access": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                "message_count": 0,
            }
        },
    }
    (storage / "2024" / "01").mkdir(parents=True)
    (storage / "2024" / "01" / "old001.json").write_text(json.dumps({
        "version": 2,
        "session_id": "old001",
        "created_at": (datetime.utcnow() - timedelta(days=365)).isoformat(),
        "last_access": (datetime.utcnow() - timedelta(days=365)).isoformat(),
        "messages": [],
        "runs": [],
    }))
    (storage / "_index.json").write_text(json.dumps(payload))
    store = SessionStore(storage_path=storage)
    assert store.get("old001") is not None
    assert "old001" in store._sessions


def test_session_store_list_sorders_by_last_access(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s1 = store.create()
    s1.add_user_message("first")
    s1.last_access = datetime.utcnow() - timedelta(hours=2)
    store.save()
    s2 = store.create()
    s2.add_user_message("second")
    s2.last_access = datetime.utcnow() - timedelta(hours=1)
    store.save()
    s3 = store.create()
    s3.add_user_message("third")
    s3.last_access = datetime.utcnow()
    store.save()

    sessions = store.list_sessions()
    assert [s.session_id for s in sessions] == [s3.session_id, s2.session_id, s1.session_id]


def test_session_store_list_sessions_counts_messages(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    s.add_user_message("u1")
    s.add_assistant_message("a1")
    s.add_user_message("u2")
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert len(sessions[0].messages) == 3


def test_session_store_load_handles_garbage_index(tmp_path: Path):
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)
    (storage / "_index.json").write_text("{not valid json")
    store = SessionStore(storage_path=storage)
    assert store._sessions == {}


def test_session_store_load_rebuilds_index_from_disk(tmp_path: Path):
    storage = _storage(tmp_path)
    (storage / "2025" / "03").mkdir(parents=True)
    (storage / "2025" / "03" / "abc123456789.json").write_text(json.dumps({
        "version": 2,
        "session_id": "abc123456789",
        "created_at": datetime.utcnow().isoformat(),
        "last_access": datetime.utcnow().isoformat(),
        "messages": [],
        "runs": [],
    }))
    store = SessionStore(storage_path=storage)
    assert "abc123456789" in store._sessions
    assert (storage / "_index.json").exists()
    index = json.loads((storage / "_index.json").read_text())
    assert "abc123456789" in index["index"]


def test_session_store_create_assigns_unique_id(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s1 = store.create()
    s2 = store.create()
    assert s1.session_id != s2.session_id
    assert len(s1.session_id) == 12


def test_session_placed_in_year_month_subdir(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    rel = store._session_relpath(s)
    parts = rel.split("/")
    assert len(parts) == 3
    assert parts[0] == f"{s.created_at.year:04d}"
    assert parts[1] == f"{s.created_at.month:02d}"
    assert parts[2] == f"{s.session_id}.json"
    assert (storage / rel).exists()


def test_session_store_index_tracks_message_count(tmp_path: Path):
    storage = _storage(tmp_path)
    store = SessionStore(storage_path=storage)
    s = store.create()
    s.add_user_message("u1")
    s.add_assistant_message("a1")
    store.save()
    index = json.loads((storage / "_index.json").read_text())
    assert index["index"][s.session_id]["message_count"] == 2


def test_session_store_migrates_legacy_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("server.sessions._LEGACY_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr("server.sessions._LEGACY_BACKUP_FILE", tmp_path / "sessions.json.bak")
    legacy_payload = {
        "version": 1,
        "sessions": [
            {
                "session_id": "legacy01",
                "created_at": datetime.utcnow().isoformat(),
                "last_access": datetime.utcnow().isoformat(),
                "messages": [
                    {"role": "user", "content": "hi", "timestamp": datetime.utcnow().isoformat()},
                ],
                "runs": [],
            }
        ],
    }
    (tmp_path / "sessions.json").write_text(json.dumps(legacy_payload))
    storage = tmp_path / "sessions"
    store = SessionStore(storage_path=storage)
    assert store.get("legacy01") is not None
    assert not (tmp_path / "sessions.json").exists()
    assert (tmp_path / "sessions.json.bak").exists()
