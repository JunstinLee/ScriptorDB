"""登录凭证 store：keyring 序列化往返 / 删除 / 损坏容忍。"""

from __future__ import annotations

import json

import config.credential_store as store

WS = "ws-test"
SITE = "accounts.example.com"


def _service() -> str:
    return f"scriptordb:{WS}:site_credential"


# ---------- store: 序列化往返 / 删除 / 损坏 ----------


def test_store_roundtrip_with_match_hints(fake_keyring):
    spec = {
        "site": SITE,
        "username": "alice",
        "password": "s3cret",
        "extra": {
            "field_label": "User ID",
            "value": "A-1001",
            "match_hints": {"name": "userid", "id": "user_id", "label": "User ID"},
        },
    }
    store.save_site_credential(WS, spec)

    raw = fake_keyring.store[_service()][SITE]
    payload = json.loads(raw)
    assert payload["version"] == 1
    assert payload["site"] == SITE
    assert payload["username"] == "alice"
    assert payload["password"] == "s3cret"
    assert payload["extra"]["field_label"] == "User ID"
    assert payload["extra"]["value"] == "A-1001"
    assert payload["extra"]["match_hints"] == {
        "name": "userid",
        "id": "user_id",
        "label": "User ID",
    }
    # updated_at 为 ISO 8601 UTC（+00:00 后缀）
    assert payload["updated_at"].endswith("+00:00")

    loaded = store.get_site_credential(WS, SITE)
    assert loaded == payload


def test_store_roundtrip_without_extra(fake_keyring):
    store.save_site_credential(WS, {"site": SITE, "username": "bob", "password": "pw"})
    loaded = store.get_site_credential(WS, SITE)
    assert loaded is not None
    assert loaded["username"] == "bob"
    assert "extra" not in loaded


def test_store_workspace_scoped_service(fake_keyring):
    store.save_site_credential(WS, {"site": SITE, "username": "a", "password": "p"})
    other = f"scriptordb:ws-other:site_credential"
    assert SITE not in fake_keyring.store.get(other, {})
    assert store.has_site_credential("ws-other", SITE) is False


def test_store_delete(fake_keyring):
    store.save_site_credential(WS, {"site": SITE, "username": "a", "password": "p"})
    assert store.has_site_credential(WS, SITE) is True
    store.delete_site_credential(WS, SITE)
    assert store.has_site_credential(WS, SITE) is False
    # 幂等：不存在也成功
    store.delete_site_credential(WS, SITE)


def test_store_corrupted_json_returns_none_and_logs(fake_keyring, monkeypatch):
    fake_keyring.set_password(_service(), SITE, "{not json")
    warnings: list[str] = []
    monkeypatch.setattr(
        store.logger, "warning", lambda msg, *a: warnings.append(msg % a if a else msg)
    )
    assert store.get_site_credential(WS, SITE) is None
    assert store.has_site_credential(WS, SITE) is False
    assert any("corrupted" in w for w in warnings)


def test_store_unsupported_version_returns_none(fake_keyring):
    fake_keyring.set_password(
        _service(), SITE, json.dumps({"version": 99, "site": SITE})
    )
    assert store.get_site_credential(WS, SITE) is None


def test_store_overwrite_is_idempotent(fake_keyring):
    store.save_site_credential(
        WS, {"site": SITE, "username": "a", "password": "one"}
    )
    store.save_site_credential(
        WS, {"site": SITE, "username": "b", "password": "two"}
    )
    loaded = store.get_site_credential(WS, SITE)
    assert loaded is not None
    assert loaded["username"] == "b"
    assert loaded["password"] == "two"

