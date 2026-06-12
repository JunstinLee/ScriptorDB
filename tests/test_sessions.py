from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from server.sessions import SESSION_TTL, Session, SessionStore


def test_session_store_create_persists(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s = store.create()
    assert s.session_id in store._sessions
    assert storage.exists()


def test_session_store_save_load_roundtrip(tmp_path: Path):
    storage = tmp_path / "sessions.json"
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
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s = store.create()
    store.delete(s.session_id)
    store2 = SessionStore(storage_path=storage)
    assert store2.get(s.session_id) is None


def test_session_store_skips_expired_on_load(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    payload = {
        "version": 1,
        "sessions": [
            {
                "session_id": "expired01",
                "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "last_access": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "messages": [],
            }
        ],
    }
    storage.write_text(json.dumps(payload))
    store = SessionStore(storage_path=storage)
    assert store.get("expired01") is None
    assert "expired01" not in store._sessions


def test_session_store_list_sorders_by_last_access(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s1 = store.create()
    s1.add_user_message("first")
    s1.last_access = datetime.utcnow() - timedelta(hours=2)
    s2 = store.create()
    s2.add_user_message("second")
    s2.last_access = datetime.utcnow() - timedelta(hours=1)
    s3 = store.create()
    s3.add_user_message("third")
    s3.last_access = datetime.utcnow()
    store.save()

    sessions = store.list_sessions()
    assert [s.session_id for s in sessions] == [s3.session_id, s2.session_id, s1.session_id]


def test_session_store_list_sessions_counts_messages(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s = store.create()
    s.add_user_message("u1")
    s.add_assistant_message("a1")
    s.add_user_message("u2")
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert len(sessions[0].messages) == 3


def test_session_store_load_handles_garbage_file(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    storage.write_text("{not valid json")
    store = SessionStore(storage_path=storage)
    assert store._sessions == {}


def test_session_store_load_skips_invalid_entries(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    payload = {
        "version": 1,
        "sessions": [
            {"session_id": "good01", "created_at": datetime.utcnow().isoformat(),
             "last_access": datetime.utcnow().isoformat(), "messages": []},
            "not a dict",
            {"created_at": datetime.utcnow().isoformat(), "last_access": datetime.utcnow().isoformat()},
        ],
    }
    storage.write_text(json.dumps(payload))
    store = SessionStore(storage_path=storage)
    assert "good01" in store._sessions
    assert len(store._sessions) == 1


def test_session_get_returns_none_for_expired_and_removes(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s = store.create()
    s.last_access = datetime.utcnow() - SESSION_TTL - timedelta(minutes=1)
    store.save()
    assert store.get(s.session_id) is None
    assert s.session_id not in store._sessions
    store2 = SessionStore(storage_path=storage)
    assert s.session_id not in store2._sessions


def test_session_store_create_assigns_unique_id(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s1 = store.create()
    s2 = store.create()
    assert s1.session_id != s2.session_id
    assert len(s1.session_id) == 12


def test_session_store_cleanup_expired(tmp_path: Path):
    storage = tmp_path / "sessions.json"
    store = SessionStore(storage_path=storage)
    s1 = store.create()
    s1.last_access = datetime.utcnow() - SESSION_TTL - timedelta(minutes=1)
    s2 = store.create()
    removed = store.cleanup_expired()
    assert removed == 1
    assert s1.session_id not in store._sessions
    assert s2.session_id in store._sessions
