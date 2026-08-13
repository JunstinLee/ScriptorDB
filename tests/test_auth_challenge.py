from __future__ import annotations

from types import SimpleNamespace

import pytest

from browser.manager import BrowserManager


def _response(url: str, status: int, headers: dict[str, str] | None = None):
    return SimpleNamespace(url=url, status=status, headers=headers or {})


@pytest.fixture
def manager() -> BrowserManager:
    return BrowserManager()


def test_flag_api(manager: BrowserManager):
    assert not manager.auth_challenge_pending()
    assert manager.auth_challenge_origin() is None

    manager.record_auth_challenge("example.com")
    assert manager.auth_challenge_pending()
    assert manager.auth_challenge_origin() == "example.com"

    # 只有匹配 origin 才能清除
    manager.clear_auth_challenge("other.com")
    assert manager.auth_challenge_pending()
    manager.clear_auth_challenge("example.com")
    assert not manager.auth_challenge_pending()


def test_401_with_challenge_header_sets_flag(manager: BrowserManager):
    manager._on_page_response(_response(
        "https://the-internet.herokuapp.com/download/file.txt",
        401,
        {"www-authenticate": 'Basic realm="Fake Realm"'},
    ))
    assert manager.auth_challenge_pending()
    assert manager.auth_challenge_origin() == "the-internet.herokuapp.com"


@pytest.mark.parametrize("status", [401, 407])
def test_www_authenticate_header_case_insensitive(manager: BrowserManager, status: int):
    manager._on_page_response(_response(
        "https://example.com/", status, {"WWW-Authenticate": "Basic realm=x"},
    ))
    assert manager.auth_challenge_pending()


def test_401_without_challenge_header_sets_nothing(manager: BrowserManager):
    manager._on_page_response(_response("https://example.com/", 401, {}))
    assert not manager.auth_challenge_pending()


def test_success_response_clears_challenge(manager: BrowserManager):
    manager.record_auth_challenge("example.com")
    manager._on_page_response(_response("https://example.com/download/file.txt", 200))
    assert not manager.auth_challenge_pending()


@pytest.mark.parametrize("status", [200, 301, 404, 500])
def test_any_non_auth_response_clears_challenge(manager: BrowserManager, status: int):
    # 非 401/407 响应意味着请求已通过认证门禁
    manager.record_auth_challenge("example.com")
    manager._on_page_response(_response(f"https://example.com/x", status))
    assert not manager.auth_challenge_pending()


def test_other_origin_response_does_not_clear(manager: BrowserManager):
    manager.record_auth_challenge("example.com")
    manager._on_page_response(_response("https://cdn.other.com/img.png", 200))
    assert manager.auth_challenge_pending()
    assert manager.auth_challenge_origin() == "example.com"


def test_new_challenge_overwrites_origin(manager: BrowserManager):
    manager.record_auth_challenge("example.com")
    manager._on_page_response(_response(
        "https://other.com/", 401, {"www-authenticate": "Basic realm=x"},
    ))
    assert manager.auth_challenge_origin() == "other.com"


def test_origin_normalization_strips_userinfo_and_port(manager: BrowserManager):
    manager.record_auth_challenge("example.com")
    # 用户信息与端口不应影响 origin 匹配
    manager._on_page_response(_response(
        "http://admin:admin@example.com:8080/download", 200,
    ))
    assert not manager.auth_challenge_pending()
