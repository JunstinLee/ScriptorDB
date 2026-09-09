from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from runtime.redact import register_password
from tests.conftest import _make_ctx
from tools.browser import browser_evaluate, browser_fill, browser_query

pytestmark = pytest.mark.usefixtures("cleanup_browser")

_PWD = "SuperSecretPassword!"
_URL = "https://accounts.example.com/login"


def _page_mock():
    page = AsyncMock()
    page.url = _URL
    return page


class TestBrowserQueryPasswordGuard:
    """browser_query 读密码控件 value：返回占位，不读 DOM。"""

    @pytest.mark.asyncio
    async def test_query_value_on_password_field_returns_placeholder(self, monkeypatch):
        """is_password_control 命中：占位返回，query_attr 不被调用。"""
        import browser.runtime as runtime_mod
        import browser.sensitive as sensitive_mod

        monkeypatch.setattr(
            sensitive_mod, "is_password_control", AsyncMock(return_value=True)
        )
        query_attr = AsyncMock(return_value=_PWD)
        monkeypatch.setattr(runtime_mod, "query_attr", query_attr)
        with patch.object(get_manager(), "_page", _page_mock()):
            result = await browser_query(_make_ctx(), "#password", attribute="value")
        assert result == "[redacted: password field]"
        query_attr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_query_all_password_field_placeholder(self, monkeypatch):
        """all=True 首元素命中密码控件：整组返回占位。"""
        import browser.runtime as runtime_mod
        import browser.sensitive as sensitive_mod

        monkeypatch.setattr(
            sensitive_mod, "is_password_control", AsyncMock(return_value=True)
        )
        query_attr_all = AsyncMock(return_value=f"[0] {_PWD}")
        monkeypatch.setattr(runtime_mod, "query_attr_all", query_attr_all)
        with patch.object(get_manager(), "_page", _page_mock()):
            result = await browser_query(
                _make_ctx(), "input", attribute="value", all=True
            )
        assert result == "[redacted: password field]"
        query_attr_all.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_query_non_password_control_passes_through(self, monkeypatch):
        """非密码控件读 value：放行，正常读取。"""
        import browser.sensitive as sensitive_mod

        monkeypatch.setattr(
            sensitive_mod, "is_password_control", AsyncMock(return_value=False)
        )
        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="hello")
        page = _page_mock()
        page.query_selector = AsyncMock(return_value=mock_element)
        with patch.object(get_manager(), "_page", page):
            result = await browser_query(_make_ctx(), "input", attribute="value")
        assert "hello" in result


class TestBrowserEvaluatePasswordGuard:
    """browser_evaluate：脚本含系统密码拒绝执行；结果过脱敏。"""

    @pytest.mark.asyncio
    async def test_evaluate_script_with_password_rejected(self, monkeypatch):
        """js 含系统密码：拒绝，页面脚本不执行。"""
        import browser.sensitive as sensitive_mod

        monkeypatch.setattr(
            sensitive_mod, "current_site_password", lambda url, ws: _PWD
        )
        page = _page_mock()
        with patch.object(get_manager(), "_page", page):
            result = await browser_evaluate(
                _make_ctx(),
                f"document.querySelector('#password').value = '{_PWD}'",
            )
        assert "拒绝" in result
        assert "密码" in result
        page.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_evaluate_result_redacted(self, monkeypatch):
        """无密码 js 执行：结果中读回的密码明文被替换。"""
        import browser.sensitive as sensitive_mod

        register_password(_PWD)
        monkeypatch.setattr(
            sensitive_mod, "current_site_password", lambda url, ws: _PWD
        )
        page = _page_mock()
        page.evaluate = AsyncMock(return_value=_PWD)
        with patch.object(get_manager(), "_page", page):
            result = await browser_evaluate(
                _make_ctx(), "document.querySelector('#password').value"
            )
        assert _PWD not in result
        assert "[redacted: password]" in result

    @pytest.mark.asyncio
    async def test_evaluate_without_site_password_passes(self, monkeypatch):
        """站点无系统凭证：js 照常执行。"""
        import browser.sensitive as sensitive_mod

        monkeypatch.setattr(
            sensitive_mod, "current_site_password", lambda url, ws: None
        )
        page = _page_mock()
        page.evaluate = AsyncMock(return_value="42")
        with patch.object(get_manager(), "_page", page):
            result = await browser_evaluate(_make_ctx(), "1 + 1")
        assert "42" in result
        page.evaluate.assert_awaited_once()


class TestBrowserFillPasswordGuard:
    """browser_fill 密码控件 + 系统密码：跳过填充，不二次填写。"""

    @pytest.mark.asyncio
    async def test_fill_system_password_skipped(self, monkeypatch):
        """is_password_control 命中且文本=系统密码：跳过，返回提示。"""
        import browser.sensitive as sensitive_mod

        register_password(_PWD)
        monkeypatch.setattr(
            sensitive_mod, "current_site_password", lambda url, ws: _PWD
        )
        monkeypatch.setattr(
            sensitive_mod, "is_password_control", AsyncMock(return_value=True)
        )
        page = _page_mock()
        page.fill = AsyncMock()
        with patch.object(get_manager(), "_page", page):
            result = await browser_fill(_make_ctx(), "#password", _PWD)
        assert "已由系统自动填充" in result
        page.fill.assert_not_awaited()
