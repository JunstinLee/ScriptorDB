from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

import config.credential_store as store
import config.secrets as secrets
import services.login_credential_service as service
from schemas.login_credential import (
    ExtraCredential,
    LoginCredentialSpec,
    MatchHints,
    SiteStatusRequest,
)

WS = "ws-test"
SITE = "accounts.example.com"


class FakeKeyring:
    def __init__(self) -> None:
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
    monkeypatch.setattr(store, "keyring", fake)
    monkeypatch.setattr(secrets, "keyring", fake)
    return fake


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


# ---------- service: 站点识别 / 校验 / 状态组装 ----------


def _spec(**overrides) -> LoginCredentialSpec:
    base = {
        "site": SITE,
        "url": f"https://{SITE}/login",
        "username": "alice",
        "password": "s3cret",
    }
    base.update(overrides)
    return LoginCredentialSpec(**base)


def test_service_save_returns_status_without_secrets(fake_keyring):
    status = service.save(WS, _spec())
    assert status.configured is True
    assert status.site == SITE
    assert status.site_label == SITE
    assert status.extra_field_label is None
    # 响应不含任何明文字段
    assert status.model_dump().get("password") is None
    assert status.model_dump().get("username") is None
    # keyring 中真实持久化
    assert store.has_site_credential(WS, SITE) is True


def test_service_site_status_true_false(fake_keyring):
    # 未配置 → 200 语义（configured=false）
    st = service.site_status(WS, SiteStatusRequest(url=f"https://{SITE}/login"))
    assert st.configured is False
    assert st.site == SITE

    service.save(WS, _spec())
    st = service.site_status(WS, SiteStatusRequest(url=f"https://{SITE}/login"))
    assert st.configured is True
    assert st.site == SITE


def test_service_netloc_normalization_www_kept(fake_keyring):
    # 站点标识：netloc_of 语义，去端口/小写/userinfo，不去 www 子域
    site = service._resolve_site(
        _spec(site="https://www.Example.com:8443/", url="https://www.example.com/login")
    )
    assert site == "www.example.com"


def test_service_site_url_mismatch_raises(fake_keyring):
    with pytest.raises(ValueError):
        service.save(
            WS,
            _spec(site="accounts.example.com", url="https://other.example.org/login"),
        )


def test_service_site_fallback_to_url(fake_keyring):
    spec = _spec(site=None)
    status = service.save(WS, spec)
    assert status.site == SITE


def test_service_missing_site_and_url_raises(fake_keyring):
    with pytest.raises(ValueError):
        service.save(WS, _spec(site=None, url=None))


def test_service_empty_username_password_raise(fake_keyring):
    with pytest.raises(ValueError, match="username"):
        service.save(WS, _spec(username="  "))
    with pytest.raises(ValueError, match="password"):
        service.save(WS, _spec(password=""))


def test_service_extra_empty_field_label_ignored(fake_keyring):
    # 带 extra 且 field_label 空 → 忽略整个 extra 槽位（等价 extra=None）
    status = service.save(
        WS, _spec(extra=ExtraCredential(field_label="", value="A-1001"))
    )
    assert status.extra_field_label is None
    payload = store.get_site_credential(WS, SITE)
    assert payload is not None
    assert "extra" not in payload


def test_service_extra_value_empty_raises(fake_keyring):
    with pytest.raises(ValueError, match="extra value"):
        service.save(
            WS,
            _spec(
                extra=ExtraCredential(
                    field_label="User ID", value="", match_hints=MatchHints()
                )
            ),
        )


def test_service_extra_label_returned_in_status(fake_keyring):
    status = service.save(
        WS,
        _spec(
            extra=ExtraCredential(
                field_label="User ID",
                value="A-1001",
                match_hints=MatchHints(name="userid", id="user_id"),
            )
        ),
    )
    assert status.extra_field_label == "User ID"
    payload = store.get_site_credential(WS, SITE)
    assert payload is not None
    assert payload["extra"]["match_hints"]["name"] == "userid"


def test_service_delete_idempotent(fake_keyring):
    service.save(WS, _spec())
    service.delete(WS, SITE)
    assert store.has_site_credential(WS, SITE) is False
    # 不存在也成功
    service.delete(WS, SITE)


# ---------- route: HTTP 语义 ----------


@pytest.fixture
def route_client(monkeypatch):
    """构造无 ASGI 的 route handler 直接调用环境：mock require_workspace。"""
    from api.routes import login_credentials as route_mod

    monkeypatch.setattr(
        route_mod,
        "require_workspace",
        lambda: type("Cfg", (), {"workspace_id": WS})(),
    )
    return route_mod


async def test_route_site_status(route_client):
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is False

    await route_client.save_credential(_spec())
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is True


async def test_route_save_then_status_flip(route_client):
    await route_client.save_credential(_spec())
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is True
    assert res.extra_field_label is None


async def test_route_missing_url_400(route_client):
    with pytest.raises(HTTPException) as ei:
        await route_client.save_credential(_spec(site=None, url=None))
    assert ei.value.status_code == 400


async def test_route_empty_username_400(route_client):
    with pytest.raises(HTTPException) as ei:
        await route_client.save_credential(_spec(username=""))
    assert ei.value.status_code == 400


async def test_route_delete_idempotent(route_client):
    assert await route_client.delete_credential(SITE) == {"ok": True, "site": SITE}
    await route_client.save_credential(_spec())
    assert await route_client.delete_credential(SITE) == {"ok": True, "site": SITE}
    assert store.has_site_credential(WS, SITE) is False
