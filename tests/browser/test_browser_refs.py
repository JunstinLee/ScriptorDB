"""元素引用（ref）生命周期：铸造、执行期校验、失效挂点、run 作用域。

覆盖：
- 同页同 URL 同签名复用 ref → 命中；
- 点击触发跳转致 ``page.url`` 变化 → ``stale_ref``；
- 元素签名变化 → ``stale_ref``；
- 显式导航（``record_navigate``）后 ref 失效；
- ``run_id`` 取自铸造方（``deps.run_id``），逻辑 run 内恒定。
"""

from __future__ import annotations

import pytest

from browser import refs
from browser.manager import BrowserManager
from schemas import ToolResult
from tools.browser_tools import actions as actions_mod


class _Handle:
    def __init__(self, signature: str) -> None:
        self._signature = signature

    async def evaluate(self, expression: str, arg=None) -> str:
        return self._signature


class _Page:
    def __init__(self, url: str, handle: _Handle | None = None) -> None:
        self.url = url
        self._handle = handle
        self.queried: list[str] = []

    def is_closed(self) -> bool:
        return False

    async def query_selector(self, selector: str):
        self.queried.append(selector)
        return self._handle


class _Manager:
    def record_action(self, *args, **kwargs) -> None:
        pass


@pytest.fixture(autouse=True)
def _clean_refs():
    refs.invalidate_all()
    yield
    refs.invalidate_all()


class TestResolveRefTarget:
    """执行期用铸造时的 page 重解析并校验 URL + 签名。"""

    @pytest.mark.asyncio
    async def test_same_url_same_signature_hits(self):
        """同页同 URL 同签名 → 返回 (page, locator)，且不重新扫描页面。"""
        page = _Page("https://example.com/a", _Handle("sig-1"))
        ref = refs.mint_ref(page, "#go", "sig-1", "run-1")
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[0] is page
        assert target[1] == "#go"
        assert page.queried == ["#go"]

    @pytest.mark.asyncio
    async def test_url_change_is_stale(self):
        """铸造后 page.url 变化（点击触发整页跳转）→ stale_ref。"""
        page = _Page("https://example.com/a", _Handle("sig-1"))
        ref = refs.mint_ref(page, "#go", "sig-1", "run-1")
        page.url = "https://example.com/b"
        result = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"

    @pytest.mark.asyncio
    async def test_signature_change_is_stale(self):
        """元素签名变化 → stale_ref。"""
        page = _Page("https://example.com/a", _Handle("sig-2"))
        ref = refs.mint_ref(page, "#go", "sig-1", "run-1")
        result = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"

    @pytest.mark.asyncio
    async def test_missing_element_is_stale(self):
        """locator 解析不到元素 → stale_ref。"""
        page = _Page("https://example.com/a", _Handle(None))
        page._handle = None
        ref = refs.mint_ref(page, "#go", "sig-1", "run-1")
        result = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"

    @pytest.mark.asyncio
    async def test_unknown_ref_is_stale(self):
        """未知 ref → stale_ref。"""
        result = await actions_mod._resolve_ref_target(_Manager(), "ref_nope")
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"


class TestInvalidationHooks:
    """失效挂点：显式导航与页面重置。"""

    def test_record_navigate_invalidates_page(self):
        """显式导航后该页 ref 立即失效。"""
        manager = BrowserManager()
        page = _Page("https://example.com/a")
        manager._page = page
        ref = refs.mint_ref(page, "#go", "sig", "run-1")
        manager.record_navigate("https://example.com/next", "Next")
        assert refs.resolve_ref(ref) is None

    def test_reset_state_invalidates_all(self):
        """reset_state 清空全部 ref。"""
        page = _Page("https://example.com/a")
        ref = refs.mint_ref(page, "#go", "sig", "run-1")
        BrowserManager().reset_state()
        assert refs.resolve_ref(ref) is None


class TestRefScope:
    """run 身份：ref 绑定 deps.run_id，逻辑 run 内恒定。"""

    @pytest.mark.asyncio
    async def test_ref_survives_ctx_run_id_change(self):
        """审批恢复换新 ``ctx.run_id`` 后，旧 ref 仍可解析（run_id 取自铸造方）。"""
        page = _Page("https://example.com/a", _Handle("sig-1"))
        ref = refs.mint_ref(page, "#go", "sig-1", "logical-run")
        record = refs.resolve_ref(ref)
        assert record is not None
        assert record.run_id == "logical-run"
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
