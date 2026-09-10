from __future__ import annotations

import pytest

from browser import get_manager
from browser.login_state import detect_login_state, netloc_of
from tests.conftest import _make_ctx  # noqa: F401  (fixture 注册)

pytestmark = pytest.mark.usefixtures("cleanup_browser")


class _FakeContext:
    def __init__(self, cookies: list[dict]):
        self._cookies = cookies

    async def cookies(self, urls=None):
        return list(self._cookies)


class _FakePage:
    def __init__(self, url: str, cookies: list[dict] | None = None,
                 title: str = "", has_password: bool = False):
        self.url = url
        self._title = title
        self._has_password = has_password
        self.context = _FakeContext(cookies or [])

    async def title(self) -> str:
        return self._title

    async def evaluate(self, expression: str, arg=None) -> bool:
        return self._has_password


class TestNetloc:
    def test_simple(self):
        assert netloc_of("https://example.com/path") == "example.com"

    def test_port_and_case(self):
        assert netloc_of("https://EXample.com:8080/x") == "example.com"

    def test_userinfo_stripped(self):
        assert netloc_of("https://user:pass@example.com/") == "example.com"

    def test_blank(self):
        assert netloc_of("about:blank") == ""


class TestDetectLoginState:
    async def test_blank_page_unknown(self):
        state = await detect_login_state(_FakePage("about:blank"))
        assert state.status == "unknown"
        assert "无有效域名" in state.reason

    async def test_expected_cookies_present_logged_in(self):
        page = _FakePage(
            "https://example.com/dashboard",
            cookies=[{"name": "session", "domain": "example.com"},
                     {"name": "csrf", "domain": "example.com"}],
        )
        state = await detect_login_state(page, expected_cookie_names=["session", "csrf"])
        assert state.status == "logged_in"
        assert "仍存在 (2/2)" in state.reason
        assert state.session_cookies == ["session", "csrf"]

    async def test_expected_cookies_partial_logged_in(self):
        page = _FakePage(
            "https://example.com/dashboard",
            cookies=[{"name": "csrf", "domain": "example.com"}],
        )
        state = await detect_login_state(page, expected_cookie_names=["session", "csrf"])
        assert state.status == "logged_in"
        assert "仍存在 (1/2)" in state.reason

    async def test_expected_cookies_all_missing_logged_out(self):
        page = _FakePage("https://example.com/dashboard", cookies=[{"name": "tracker"}])
        state = await detect_login_state(page, expected_cookie_names=["session", "csrf"])
        assert state.status == "logged_out"
        assert "全部缺失" in state.reason

    async def test_login_url_logged_out(self):
        page = _FakePage("https://example.com/login", cookies=[{"name": "tracker"}])
        state = await detect_login_state(page)
        assert state.status == "logged_out"
        assert state.on_login_page is True
        assert "URL 指向登录路径" in state.reason

    async def test_title_and_password_form_logged_out(self):
        page = _FakePage(
            "https://example.com/welcome",
            cookies=[{"name": "tracker"}],
            title="Sign in to Example",
            has_password=True,
        )
        state = await detect_login_state(page)
        assert state.status == "logged_out"
        assert "密码输入框" in state.reason

    async def test_title_keyword_without_password_ignored(self):
        page = _FakePage(
            "https://example.com/welcome",
            cookies=[{"name": "tracker"}],
            title="Sign in to Example",
            has_password=False,
        )
        state = await detect_login_state(page)
        assert state.status == "logged_in"

    async def test_cookies_present_logged_in_heuristic(self):
        page = _FakePage(
            "https://example.com/dashboard",
            cookies=[{"name": "session", "domain": "example.com"}],
        )
        state = await detect_login_state(page)
        assert state.status == "logged_in"
        assert "1 个域名 cookie" in state.reason

    async def test_no_cookies_not_login_page_unknown(self):
        page = _FakePage("https://example.com/dashboard")
        state = await detect_login_state(page)
        assert state.status == "unknown"
        assert "需访问受保护页面" in state.reason

    async def test_explicit_domain_on_blank_page(self):
        page = _FakePage("about:blank", cookies=[{"name": "session", "domain": "example.com"}])
        state = await detect_login_state(page, domain="example.com")
        assert state.status == "logged_in"
        assert state.domain == "example.com"


class TestValidateProfile:
    async def test_profile_missing_unknown(self, monkeypatch):
        from browser import profiles as profiles_mod

        monkeypatch.setattr(profiles_mod, "get_browser_profile", lambda ws, name: None)
        state = await profiles_mod.validate_profile(get_manager(), "ghost", "ws1")
        assert state.status == "unknown"
        assert "不存在" in state.reason

    async def test_browser_not_launched(self, monkeypatch):
        from browser import profiles as profiles_mod

        monkeypatch.setattr(
            profiles_mod, "get_browser_profile",
            lambda ws, name: {"cookies": [{"name": "session"}]},
        )
        with pytest.raises(profiles_mod.BrowserNotLaunchedError):
            await profiles_mod.validate_profile(get_manager(), "p", "ws1")

    async def test_valid_profile_logged_in(self, monkeypatch):
        from browser import profiles as profiles_mod

        storage = {"cookies": [{"name": "session", "domain": "example.com"}]}
        monkeypatch.setattr(profiles_mod, "get_browser_profile", lambda ws, name: storage)
        page = _FakePage("https://example.com/dashboard", cookies=[{"name": "session"}])
        monkeypatch.setattr(get_manager(), "_page", page)

        state = await profiles_mod.validate_profile(get_manager(), "p", "ws1")
        assert state.status == "logged_in"

    async def test_domain_fallback_from_profile_cookies(self, monkeypatch):
        from browser import profiles as profiles_mod

        storage = {
            "cookies": [
                {"name": "session", "domain": ".example.com"},
                {"name": "csrf", "domain": ".example.com"},
            ]
        }
        monkeypatch.setattr(profiles_mod, "get_browser_profile", lambda ws, name: storage)
        page = _FakePage("about:blank", cookies=[{"name": "session", "domain": "example.com"}])
        monkeypatch.setattr(get_manager(), "_page", page)

        state = await profiles_mod.validate_profile(get_manager(), "p", "ws1")
        assert state.status == "logged_in"
        assert state.domain == "example.com"
