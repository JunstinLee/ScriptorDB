"""browser_locate 三态与输出降级阶梯。

覆盖：
- ``_confirm_actionable`` 把候选判成 usable / blocked(原因) / unverified 三态；
- ``browser_locate`` 主输出只含 usable，为空时才降级输出带 [unverified] 的兜底，
  blocked 条目被省略；
- 确认阶段的候选上限（成本控制）与「enabled 不再被覆写」的契约。
"""

from __future__ import annotations

from typing import Any

import pytest

from browser.runtime import MAX_CONFIRM_CANDIDATES, _confirm_actionable
from tools.browser_tools import dom as dom_mod
from tools.browser_tools.dom import browser_locate

pytestmark = pytest.mark.usefixtures("cleanup_browser")


class _Handle:
    def __init__(self, visible: bool = True, enabled: bool = True, error: Exception | None = None):
        self._visible = visible
        self._enabled = enabled
        self._error = error

    async def is_visible(self) -> bool:
        if self._error is not None:
            raise self._error
        return self._visible

    async def is_enabled(self) -> bool:
        if self._error is not None:
            raise self._error
        return self._enabled


class _Page:
    def __init__(self, handles: dict):
        self._handles = handles
        self.queries = 0

    async def query_selector(self, selector: str):
        self.queries += 1
        value = self._handles.get(selector)
        if isinstance(value, BaseException):
            raise value
        return value


def _el(selector: str, *, receives: bool = True, in_viewport: bool = True,
        in_active: bool = True, stable: bool = True) -> dict:
    return {
        "tag": "button",
        "role": "button",
        "text": selector,
        "selector": selector,
        "enabled": True,
        "receivesEvents": receives,
        "inViewport": in_viewport,
        "inActive": in_active,
        "id": "stable-id" if stable else "",
    }


class TestConfirmActionableStates:
    """_confirm_actionable 的三态判定与原因。"""

    @pytest.mark.asyncio
    async def test_resolved_and_operable_is_usable(self):
        """可见 + 可用 + 接收事件 → usable，actionable=True，无原因。"""
        el = _el("#ok")
        page: Any = _Page({"#ok": _Handle(visible=True, enabled=True)})
        await _confirm_actionable(page, [el])
        assert el["state"] == "usable"
        assert el["state_reason"] == ""
        assert el["actionable"] is True

    @pytest.mark.asyncio
    async def test_invisible_is_blocked_hidden(self):
        """解析成功但不可见 → blocked(hidden)。"""
        el = _el("#hidden")
        page: Any = _Page({"#hidden": _Handle(visible=False, enabled=True)})
        await _confirm_actionable(page, [el])
        assert el["state"] == "blocked"
        assert el["state_reason"] == "hidden"
        assert el["actionable"] is False

    @pytest.mark.asyncio
    async def test_disabled_is_blocked_disabled(self):
        """解析成功但被禁用 → blocked(disabled)。"""
        el = _el("#disabled")
        page: Any = _Page({"#disabled": _Handle(visible=True, enabled=False)})
        await _confirm_actionable(page, [el])
        assert el["state"] == "blocked"
        assert el["state_reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_covered_is_blocked_covered(self):
        """被遮挡（receivesEvents False）→ blocked(covered)。"""
        el = _el("#covered", receives=False)
        page: Any = _Page({"#covered": _Handle(visible=True, enabled=True)})
        await _confirm_actionable(page, [el])
        assert el["state"] == "blocked"
        assert el["state_reason"] == "covered"

    @pytest.mark.asyncio
    async def test_unresolved_selector_is_unverified(self):
        """query_selector 返回 None → unverified，而非 blocked。"""
        el = _el("#gone")
        page: Any = _Page({})
        await _confirm_actionable(page, [el])
        assert el["state"] == "unverified"
        assert el["state_reason"] == ""
        assert el["actionable"] is False

    @pytest.mark.asyncio
    async def test_selector_error_is_unverified(self):
        """query_selector 抛异常（非法 selector）→ unverified。"""
        el = _el("div:has(> broken")
        page: Any = _Page({"div:has(> broken": Exception("not a valid selector")})
        await _confirm_actionable(page, [el])
        assert el["state"] == "unverified"

    @pytest.mark.asyncio
    async def test_detached_handle_is_blocked_detached(self):
        """handle 存在但已脱离 DOM → blocked(detached)。"""
        el = _el("#detached")
        page: Any = _Page({"#detached": _Handle(error=Exception("Element is not attached to the DOM"))})
        await _confirm_actionable(page, [el])
        assert el["state"] == "blocked"
        assert el["state_reason"] == "detached"

    @pytest.mark.asyncio
    async def test_enabled_signal_is_not_overwritten(self):
        """``enabled`` 只保留 JS 原始信号，不再被确认结果覆写。"""
        el = _el("#x")
        el["enabled"] = True
        page: Any = _Page({"#x": _Handle(visible=False)})
        await _confirm_actionable(page, [el])
        assert el["enabled"] is True

    @pytest.mark.asyncio
    async def test_candidate_cap_limits_confirmation(self):
        """候选超过上限时按预排序截断到 MAX_CONFIRM_CANDIDATES。"""
        elements = [
            _el(f"#e{i}", in_viewport=(i % 2 == 0), stable=(i % 3 == 0))
            for i in range(MAX_CONFIRM_CANDIDATES + 40)
        ]
        page: Any = _Page({})
        await _confirm_actionable(page, elements)
        assert len(elements) == MAX_CONFIRM_CANDIDATES
        assert page.queries <= MAX_CONFIRM_CANDIDATES


class _Manager:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str]] = []

    def record_action(self, tool: str, detail: str, success: bool = True,
                      selector: str = "", coords: dict | None = None) -> None:
        self.actions.append((tool, detail))


def _stub_locate(monkeypatch, elements: list[dict]) -> _Manager:
    manager = _Manager()
    monkeypatch.setattr(dom_mod, "_require_browser", lambda: (manager, object()))
    monkeypatch.setattr(dom_mod, "_check_blocked", lambda _m: None)

    import browser.runtime as runtime_mod

    async def fake_locate(page, text: str = "", role: str = "", scope: str = "visible"):
        return elements

    monkeypatch.setattr(runtime_mod, "locate_elements", fake_locate)
    return manager


def _locate_el(selector: str, state: str, reason: str = "", text: str = "") -> dict:
    return {
        "tag": "button",
        "role": "button",
        "text": text or selector,
        "selector": selector,
        "state": state,
        "state_reason": reason,
    }


class TestBrowserLocateOutput:
    """browser_locate 的过滤 / 降级 / 标注。"""

    @pytest.mark.asyncio
    async def test_main_list_outputs_only_usable(self, monkeypatch):
        """同时存在 usable 与 unverified 时，只输出 usable，且不出现 [unverified]。"""
        elements = [
            _locate_el("#a", "usable"),
            _locate_el("#b", "unverified"),
            _locate_el("#c", "blocked", "hidden"),
        ]
        manager = _stub_locate(monkeypatch, elements)
        result = await browser_locate(_ctx(), "")
        assert "#a" in result
        assert "#b" not in result
        assert "#c" not in result
        assert "[unverified]" not in result
        tool, detail = manager.actions[-1]
        assert tool == "locate"
        assert "usable=1" in detail and "unverified=1" in detail and "blocked=1" in detail
        assert "hidden=1" in detail

    @pytest.mark.asyncio
    async def test_degrades_to_unverified_with_marker_and_count(self, monkeypatch):
        """无 usable 时降级输出 unverified，逐行带 [unverified] 并附计数说明。"""
        elements = [
            _locate_el("#u1", "unverified"),
            _locate_el("#u2", "unverified"),
            _locate_el("#b", "blocked", "covered"),
        ]
        _stub_locate(monkeypatch, elements)
        result = await browser_locate(_ctx(), "")
        lines = result.splitlines()
        assert lines[0].endswith("[unverified]")
        assert lines[1].endswith("[unverified]")
        assert "2 unverified element(s)" in result
        assert "#b" not in result

    @pytest.mark.asyncio
    async def test_blocked_only_gives_empty_hint_with_blocked_note(self, monkeypatch):
        """只有 blocked 条目：不输出条目行，空结果提示附 blocked 计数。"""
        elements = [_locate_el("#b", "blocked", "disabled")]
        _stub_locate(monkeypatch, elements)
        result = await browser_locate(_ctx(), "")
        assert "#b" not in result
        assert "No interactive elements" in result
        assert "1 matching element(s) exist" in result

    @pytest.mark.asyncio
    async def test_visible_empty_hint_points_to_wait_not_page(self, monkeypatch):
        """visible 空结果优先建议 browser_wait_for_selector，不再直接推 scope=page。"""
        _stub_locate(monkeypatch, [])
        result = await browser_locate(_ctx(), "")
        assert "browser_wait_for_selector" in result
        assert 'scope="page"' not in result

    @pytest.mark.asyncio
    async def test_page_scope_empty_hint_is_plain(self, monkeypatch):
        """page 空结果是朴素文案（不承诺可再放宽）。"""
        _stub_locate(monkeypatch, [])
        result = await browser_locate(_ctx(), "", scope="page")
        assert result.startswith("No interactive elements found.")

    @pytest.mark.asyncio
    async def test_record_action_reports_state_counts(self, monkeypatch):
        """record_action 里可见三态计数与 blocked 原因分布。"""
        elements = [
            _locate_el("#a", "usable"),
            _locate_el("#b", "blocked", "hidden"),
            _locate_el("#c", "blocked", "covered"),
        ]
        manager = _stub_locate(monkeypatch, elements)
        await browser_locate(_ctx(), "")
        detail = manager.actions[-1][1]
        assert "usable=1" in detail
        assert "blocked=2" in detail
        assert "blocked_reasons=covered=1, hidden=1" in detail


def _ctx():
    from tests.support.ctx import make_ctx

    return make_ctx()
