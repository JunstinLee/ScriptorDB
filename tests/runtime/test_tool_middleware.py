"""browser_find 重复调用熔断：隔离键、判定与输出标签。

覆盖：
- 同 run / 同 page / 同导航修订 / 同查询指纹且已成功产出 → ``find-repeat``；
- 换指纹 / 导航后 / URL 变化 / 切换标签页 / 未产出 ref → ``allow``；
- 同一逻辑 run 内 ``ctx.run_id`` 变化（审批暂停/恢复）不重置熔断；
- run 终结清理后不再命中。
"""

from __future__ import annotations

import pytest

from browser.manager import BrowserManager
from runtime import tool_middleware as mw


class _Deps:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id


class _Ctx:
    def __init__(self, *, deps_run_id: str = "run-1", ctx_run_id: str | None = None) -> None:
        self.deps = _Deps(deps_run_id)
        self.run_id = ctx_run_id


class _Page:
    def __init__(self, url: str) -> None:
        self.url = url


class _Manager:
    def __init__(self, page: _Page, nav_rev: int = 0) -> None:
        self._page = page
        self._nav_rev = nav_rev

    def page(self) -> _Page:
        return self._page

    def nav_revision(self) -> int:
        return self._nav_rev


@pytest.fixture(autouse=True)
def _clean_finds():
    mw._round_finds.clear()
    yield
    mw._round_finds.clear()


def _record(ctx, manager, *, text="", role="", scope="visible", produced=True) -> None:
    mw.record_find(
        ctx,
        page_key=mw._page_key(manager),
        page_url=mw._page_url(manager),
        nav_rev=mw._nav_revision(manager),
        fingerprint=mw._find_fingerprint(text, role, scope),
        produced=produced,
    )


def _use_manager(monkeypatch, manager: _Manager) -> None:
    import browser

    monkeypatch.setattr(browser, "get_manager", lambda: manager)


class TestFindRepeat:
    """相同查询条件的重复 find 才被拦截。"""

    @pytest.mark.asyncio
    async def test_same_query_is_repeat(self, monkeypatch):
        """同 page 同修订同指纹且已产出 → find-repeat。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="Go")

        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "find-repeat"

    @pytest.mark.asyncio
    async def test_empty_query_allowed(self, monkeypatch):
        """无 text/role 的空查询不参与熔断 → 始终 allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager)

        decision = await mw.evaluate_call(ctx, "browser_find", {"scope": "visible"})
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_different_fingerprint_allowed(self, monkeypatch):
        """查询参数不同 → allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="登录")

        decision = await mw.evaluate_call(ctx, "browser_find", {"text": "导出"})
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_navigated_page_allowed(self, monkeypatch):
        """同页再次显式导航（nav_rev 变化）→ allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="Go")

        manager._nav_rev = 1
        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_url_changed_allowed(self, monkeypatch):
        """点击触发的整页跳转（URL 变化、nav_rev 不变）→ allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="Go")

        manager._page.url = "https://example.com/b"
        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_tab_switch_allowed(self, monkeypatch):
        """切换到另一个 page 对象 → allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="Go")

        manager._page = _Page("https://example.com/a")
        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_not_produced_allowed(self, monkeypatch):
        """上次未产出 ref（无 usable 元素）→ allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager, text="Go", produced=False)

        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_containers_mode_allowed(self, monkeypatch):
        """containers 查询与 elements 记录不同，不被误拦。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, manager)

        decision = await mw.evaluate_call(ctx, "browser_find", {"mode": "containers"})
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_no_page_allowed(self, monkeypatch):
        """取不到 page → fail-open allow。"""
        manager = _Manager(None)
        _use_manager(monkeypatch, manager)
        ctx = _Ctx()
        _record(ctx, _Manager(_Page("https://example.com/a")), text="Go")

        decision = await mw.evaluate_call(
            ctx, "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"


class TestRunScope:
    """run 身份取 deps.run_id，逻辑 run 内恒定。"""

    @pytest.mark.asyncio
    async def test_survives_ctx_run_id_change(self, monkeypatch):
        """审批恢复换新 ctx.run_id，但 deps.run_id 不变 → 仍命中。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        _record(_Ctx(deps_run_id="logical", ctx_run_id="r1"), manager, text="Go")

        decision = await mw.evaluate_call(
            _Ctx(deps_run_id="logical", ctx_run_id="r2"),
            "browser_find",
            {"text": "Go", "scope": "visible"},
        )
        assert decision == "find-repeat"

    @pytest.mark.asyncio
    async def test_other_run_isolated(self, monkeypatch):
        """另一次逻辑 run 不共享状态 → allow。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        _record(_Ctx(deps_run_id="run-1"), manager, text="Go")

        decision = await mw.evaluate_call(
            _Ctx(deps_run_id="run-2"), "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"

    @pytest.mark.asyncio
    async def test_clear_run_releases_state(self, monkeypatch):
        """run 终结清理后不再命中。"""
        manager = _Manager(_Page("https://example.com/a"))
        _use_manager(monkeypatch, manager)
        _record(_Ctx(deps_run_id="run-1"), manager, text="Go")

        mw.clear_run("run-1")
        decision = await mw.evaluate_call(
            _Ctx(deps_run_id="run-1"), "browser_find", {"text": "Go", "scope": "visible"}
        )
        assert decision == "allow"


class TestFindRepeatLabel:
    """拦截时给出复用已有 ref 的替代动作。"""

    @pytest.mark.asyncio
    async def test_label_mentions_ref(self):
        label = await mw.execute_switch(None, "browser_find", {}, "find-repeat")
        assert "ref" in label


class TestNavRevision:
    """manager 的导航修订计数只由显式导航推进。"""

    def test_count_increments_on_navigate(self):
        manager = BrowserManager()
        manager._page = _Page("https://example.com/a")
        assert manager.nav_revision() == 0
        manager.record_navigate("https://example.com/a", "A")
        assert manager.nav_revision() == 1
        manager.record_navigate("https://example.com/b", "B")
        assert manager.nav_revision() == 2

    def test_count_zero_without_page(self):
        assert BrowserManager().nav_revision() == 0
