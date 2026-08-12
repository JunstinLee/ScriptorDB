from __future__ import annotations

import json

import pytest

import config.secrets as secrets


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
def fake_keyring(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(secrets, "keyring", fake)
    return fake


def _service() -> str:
    return secrets._service("ws-test") + secrets.BROWSER_PROFILE_SERVICE_SUFFIX


def _small_state() -> dict:
    return {"cookies": [{"name": "a", "value": "b", "domain": "example.com"}], "origins": []}


def _large_state() -> dict:
    cookies = [
        {
            "name": f"cookie_{i}",
            "value": "x" * 200,
            "domain": f"example{i}.com",
            "path": "/",
            "expires": 1900000000 + i,
        }
        for i in range(60)
    ]
    return {
        "cookies": cookies,
        "origins": [{"origin": "https://example.com", "localStorage": [{"name": "k", "value": "v" * 500}]}],
    }


def test_small_profile_roundtrip(fake_keyring):
    state = _small_state()
    secrets.save_browser_profile("ws-test", "alice", state)
    assert secrets.get_browser_profile("ws-test", "alice") == state


def test_large_profile_is_chunked_and_roundtrips(fake_keyring):
    state = _large_state()
    secrets.save_browser_profile("ws-test", "big", state)

    records = fake_keyring.store[_service()]
    chunk_records = [v for k, v in records.items() if k != "big"]
    assert len(chunk_records) > 1
    assert all(len(v) <= secrets.BROWSER_PROFILE_MAX_CHUNK_CHARS for v in chunk_records)

    assert secrets.get_browser_profile("ws-test", "big") == state


def test_unicode_roundtrip(fake_keyring):
    state = {
        "cookies": [{"name": "中文名", "value": "值😀", "domain": "例子.com"}],
        "origins": [{"origin": "https://例子.com", "localStorage": [{"name": "键", "value": "长文本" * 100}]}],
    }
    secrets.save_browser_profile("ws-test", "unicode", state)
    assert secrets.get_browser_profile("ws-test", "unicode") == state


def test_legacy_v1_single_record_is_readable(fake_keyring):
    state = _small_state()
    fake_keyring.set_password(_service(), "legacy", json.dumps(state))
    assert secrets.get_browser_profile("ws-test", "legacy") == state


def test_update_cleans_old_generation(fake_keyring):
    secrets.save_browser_profile("ws-test", "p", _small_state())
    records = fake_keyring.store[_service()]
    first_generation_chunks = {k for k in records if k.startswith("p:")}

    secrets.save_browser_profile("ws-test", "p", _large_state())
    records = fake_keyring.store[_service()]
    assert not first_generation_chunks.intersection(records.keys())
    assert len({k for k in records if k.startswith("p:")}) > 1
    assert secrets.get_browser_profile("ws-test", "p") == _large_state()


def test_failed_write_keeps_old_profile_and_cleans_new_chunks(fake_keyring, monkeypatch):
    secrets.save_browser_profile("ws-test", "p", _small_state())
    old = secrets.get_browser_profile("ws-test", "p")
    old_records = set(fake_keyring.store[_service()].keys())

    original = FakeKeyring.set_password

    def failing_set(self, service, username, password):
        if username != "p" and username.endswith(":1"):
            raise RuntimeError("credential too large")
        original(self, service, username, password)

    monkeypatch.setattr(FakeKeyring, "set_password", failing_set)

    with pytest.raises(secrets.BrowserProfileWriteError):
        secrets.save_browser_profile("ws-test", "p", _large_state())

    records = fake_keyring.store[_service()]
    assert set(records.keys()) == old_records
    assert secrets.get_browser_profile("ws-test", "p") == old


def _delete_first_chunk(records: dict[str, str]) -> None:
    chunk_keys = [k for k in records if k.startswith("p:")]
    del records[chunk_keys[0]]


def _bump_chunk_count(records: dict[str, str]) -> None:
    meta = json.loads(records["p"])
    meta["chunk_count"] += 1
    records["p"] = json.dumps(meta)


def _corrupt_last_chunk(records: dict[str, str]) -> None:
    chunk_keys = [k for k in records if k.startswith("p:")]
    records[chunk_keys[-1]] = "AAAA"


def _truncate_meta(records: dict[str, str]) -> None:
    records["p"] = json.dumps({"version": 2, "chunk_count": 1})


def _future_version(records: dict[str, str]) -> None:
    records["p"] = json.dumps({"version": 3, "generation": "g", "chunk_count": 1})


def _absurd_chunk_count(records: dict[str, str]) -> None:
    records["p"] = json.dumps(
        {"version": 2, "generation": "g", "chunk_count": 10**9, "sha256": "a" * 64}
    )


@pytest.mark.parametrize(
    "corrupt",
    [
        _delete_first_chunk,
        _bump_chunk_count,
        _corrupt_last_chunk,
        _truncate_meta,
        _future_version,
        _absurd_chunk_count,
    ],
)
def test_corrupted_storage_raises(fake_keyring, corrupt):
    secrets.save_browser_profile("ws-test", "p", _large_state())
    corrupt(fake_keyring.store[_service()])
    with pytest.raises(secrets.BrowserProfileCorruptedError):
        secrets.get_browser_profile("ws-test", "p")


def test_has_profile_false_when_corrupted(fake_keyring):
    secrets.save_browser_profile("ws-test", "p", _large_state())
    service = _service()
    chunk_keys = [k for k in fake_keyring.store[service] if k.startswith("p:")]
    del fake_keyring.store[service][chunk_keys[0]]
    assert secrets.has_browser_profile("ws-test", "p") is False
    assert secrets.has_browser_profile("ws-test", "missing") is False


def test_delete_v2_removes_chunks_and_meta(fake_keyring):
    secrets.save_browser_profile("ws-test", "p", _large_state())
    secrets.delete_browser_profile("ws-test", "p")
    records = fake_keyring.store[_service()]
    assert not any(k == "p" or k.startswith("p:") for k in records)
    assert secrets.get_browser_profile("ws-test", "p") is None


def test_delete_legacy_v1_removes_single_record(fake_keyring):
    fake_keyring.set_password(_service(), "legacy", json.dumps(_small_state()))
    secrets.delete_browser_profile("ws-test", "legacy")
    assert "legacy" not in fake_keyring.store[_service()]


def test_too_large_payload_raises(fake_keyring, monkeypatch):
    monkeypatch.setattr(secrets, "BROWSER_PROFILE_MAX_TOTAL_BYTES", 16)
    with pytest.raises(secrets.BrowserProfileTooLargeError):
        secrets.save_browser_profile("ws-test", "p", _small_state())
    assert secrets.get_browser_profile("ws-test", "p") is None

