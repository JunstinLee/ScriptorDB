"""登录凭证 service：站点识别 / 校验 / 状态组装。"""

from __future__ import annotations

import pytest

import config.credential_store as store
import services.login_credential_service as service
from schemas.login_credential import (
    ExtraCredential,
    MatchHints,
    SiteStatusRequest,
)
from tests.support.credentials import SITE, WS, spec


def test_service_save_returns_status_without_secrets(fake_keyring):
    status = service.save(WS, spec())
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

    service.save(WS, spec())
    st = service.site_status(WS, SiteStatusRequest(url=f"https://{SITE}/login"))
    assert st.configured is True
    assert st.site == SITE


def test_service_netloc_normalization_www_kept(fake_keyring):
    # 站点标识：netloc_of 语义，去端口/小写/userinfo，不去 www 子域
    site = service._resolve_site(
        spec(site="https://www.Example.com:8443/", url="https://www.example.com/login")
    )
    assert site == "www.example.com"


def test_service_site_url_mismatch_raises(fake_keyring):
    with pytest.raises(ValueError):
        service.save(
            WS,
            spec(site="accounts.example.com", url="https://other.example.org/login"),
        )


def test_service_site_fallback_to_url(fake_keyring):
    status = service.save(WS, spec(site=None))
    assert status.site == SITE


def test_service_missing_site_and_url_raises(fake_keyring):
    with pytest.raises(ValueError):
        service.save(WS, spec(site=None, url=None))


def test_service_empty_username_password_raise(fake_keyring):
    with pytest.raises(ValueError, match="username"):
        service.save(WS, spec(username="  "))
    with pytest.raises(ValueError, match="password"):
        service.save(WS, spec(password=""))


def test_service_extra_empty_field_label_ignored(fake_keyring):
    # 带 extra 且 field_label 空 → 忽略整个 extra 槽位（等价 extra=None）
    status = service.save(
        WS, spec(extra=ExtraCredential(field_label="", value="A-1001"))
    )
    assert status.extra_field_label is None
    payload = store.get_site_credential(WS, SITE)
    assert payload is not None
    assert "extra" not in payload


def test_service_extra_value_empty_raises(fake_keyring):
    with pytest.raises(ValueError, match="extra value"):
        service.save(
            WS,
            spec(
                extra=ExtraCredential(
                    field_label="User ID", value="", match_hints=MatchHints()
                )
            ),
        )


def test_service_extra_label_returned_in_status(fake_keyring):
    status = service.save(
        WS,
        spec(
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
    service.save(WS, spec())
    service.delete(WS, SITE)
    assert store.has_site_credential(WS, SITE) is False
    # 不存在也成功
    service.delete(WS, SITE)
