"""元素引用（ref）生命周期：铸造、执行期校验、失效挂点、run 作用域。

覆盖：
- 同页同 URL 同签名复用 ref → 命中；
- 点击触发跳转致 ``page.url`` 变化 → ``stale_ref``；
- 强定位器结构身份（tag/role）冲突 → ``stale_ref``；
- aria/text 漂移、弱定位器身份冲突 → 放行（unverified）；
- 显式导航（``record_navigate``）后 ref 失效；
- ``run_id`` 取自铸造方（``deps.run_id``），逻辑 run 内恒定。
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from browser import refs
from browser.locate_script import ELEMENT_SIGNATURE_JS
from browser.manager import BrowserManager
from runtime import tool_middleware as tm
from schemas import ToolResult
from tools.browser_tools import actions as actions_mod


class _Handle:
    def __init__(self, signature: str | None = None, error: Exception | None = None) -> None:
        self._signature = signature
        self._error = error

    async def evaluate(self, expression: str, arg=None):
        if self._error is not None:
            raise self._error
        return self._signature


class _Page:
    def __init__(self, url: str, handle: _Handle | None = None) -> None:
        self.url = url
        self._handle = handle
        self.queried: list[str] = []

    def is_closed(self) -> bool:
        return False

    async def wait_for_selector(self, selector: str, timeout: int | None = None):
        if self._handle is None:
            raise TimeoutError(f"waiting for selector {selector!r} failed")
        return self._handle

    async def query_selector(self, selector: str):
        self.queried.append(selector)
        return self._handle


class _Manager:
    def record_action(self, *args, **kwargs) -> None:
        pass


def _sig(tag: str = "button", role: str = "", aria: str = "", text: str = "") -> str:
    """构造 4 段签名（tag / role / aria / text），与 ``ELEMENT_SIGNATURE_JS`` 同格式。"""
    return "\u0001".join([tag, role, aria, text])


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
        sig = _sig(tag="button", role="button", text="Go")
        page = _Page("https://example.com/a", _Handle(sig))
        ref = refs.mint_ref(page, "#go", sig, "run-1", locator_kind="id")
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[0] is page
        assert target[1] == "#go"
        assert page.queried == ["#go"]

    @pytest.mark.asyncio
    async def test_url_change_is_stale(self):
        """铸造后 page.url 变化（点击触发整页跳转）→ stale_ref。"""
        sig = _sig(tag="button", role="button", text="Go")
        page = _Page("https://example.com/a", _Handle(sig))
        ref = refs.mint_ref(page, "#go", sig, "run-1", locator_kind="id")
        page.url = "https://example.com/b"
        result = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"

    @pytest.mark.asyncio
    async def test_signature_change_is_stale(self):
        """强定位器 + 硬身份冲突（tag / role 变）→ stale_ref。"""
        minted = _sig(tag="button", role="button", text="Go")
        current = _sig(tag="a", role="link", text="Go")
        page = _Page("https://example.com/a", _Handle(current))
        ref = refs.mint_ref(page, "#go", minted, "run-1", locator_kind="id")
        result = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(result, ToolResult)
        assert result.error.category == "stale_ref"

    @pytest.mark.asyncio
    async def test_soft_text_drift_hits(self):
        """硬身份一致、仅软文本（textContent）抖动 → 命中，不判 stale。"""
        minted = _sig(tag="button", role="button", text="Go")
        current = _sig(tag="button", role="button", text="Go now")
        page = _Page("https://example.com/a", _Handle(current))
        ref = refs.mint_ref(page, "#go", minted, "run-1", locator_kind="id")
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[1] == "#go"

    @pytest.mark.asyncio
    async def test_aria_drift_hits(self):
        """结构身份（tag/role）一致、仅 aria-label 漂移 → 命中，不判 stale。"""
        minted = _sig(tag="button", role="button", aria="Submit", text="Go")
        current = _sig(tag="button", role="button", aria="Submit search", text="Go")
        page = _Page("https://example.com/a", _Handle(current))
        ref = refs.mint_ref(page, "#go", minted, "run-1", locator_kind="id")
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[1] == "#go"

    @pytest.mark.asyncio
    async def test_weak_locator_hard_mismatch_is_unverified(self):
        """弱定位器（text / path）硬身份冲突 → 放行，且顺手失效该 ref。"""
        minted = _sig(tag="button", role="button", text="Go")
        current = _sig(tag="a", role="link", text="Go")
        page = _Page("https://example.com/a", _Handle(current))
        ref = refs.mint_ref(page, "text=Go", minted, "run-1", locator_kind="text")
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[1] == "text=Go"
        assert refs.resolve_ref(ref) is None

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
        sig = _sig(tag="button", role="button", text="Go")
        page = _Page("https://example.com/a", _Handle(sig))
        ref = refs.mint_ref(page, "#go", sig, "logical-run", locator_kind="id")
        record = refs.resolve_ref(ref)
        assert record is not None
        assert record.run_id == "logical-run"
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)


class TestResolveRefTargetUnverified:
    """签名算不出 ≠ 元素变化：宽容命中并标记 unverified。"""

    @pytest.mark.asyncio
    async def test_signature_error_is_unverified_hit(self):
        """``_element_signature`` 抛异常 → 返回 (page, locator)，不判 stale。"""
        handle = _Handle(error=RuntimeError("evaluate failed"))
        page = _Page("https://example.com/a", handle)
        ref = refs.mint_ref(
            page, "#go", _sig(tag="button", role="button", text="Go"), "run-1",
            locator_kind="id",
        )
        target = await actions_mod._resolve_ref_target(_Manager(), ref)
        assert isinstance(target, tuple)
        assert target[1] == "#go"


_NODE = shutil.which("node")


def _eval_signature_js(
    *,
    tag: str = "button",
    text_content: str = "",
    inner_text: str = "",
    attrs: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """用 node 真实执行 ``ELEMENT_SIGNATURE_JS``，返回 (默认签名, 再次默认, 显式 textVal 签名)。"""
    script = (
        f"const attrs = {json.dumps(attrs or {})};\n"
        "const el = {\n"
        f"  tagName: {json.dumps(tag)},\n"
        f"  textContent: {json.dumps(text_content)},\n"
        f"  innerText: {json.dumps(inner_text)},\n"
        "  getAttribute(name) { return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },\n"
        "};\n"
        f"const f = {ELEMENT_SIGNATURE_JS};\n"
        "const tag = (el.tagName || '').toLowerCase();\n"
        "const explicit = el.getAttribute('aria-label') || el.textContent || '';\n"
        "console.log(JSON.stringify([f(el), f(el), f(el, tag, explicit)]));\n"
    )
    completed = subprocess.run(
        [_NODE, "-e", script], capture_output=True, text=True, check=True,
    )
    first, second, explicit = json.loads(completed.stdout.strip())
    return first, second, explicit


@pytest.mark.skipif(_NODE is None, reason="node not available")
class TestSignatureRoundTrip:
    """真实签名回环：``ELEMENT_SIGNATURE_JS`` 的确定性与同源一致性。"""

    def test_signature_is_deterministic(self):
        """同一元素算两次，结果相等。"""
        first, second, _ = _eval_signature_js(tag="button", text_content="Search")
        assert first == second

    def test_innertext_change_does_not_change_signature(self):
        """``innerText`` 变但 ``textContent`` 不变 → 签名不判 stale。"""
        base, _, _ = _eval_signature_js(
            tag="button", text_content="Search", inner_text="Search",
        )
        moved, _, _ = _eval_signature_js(
            tag="button", text_content="Search", inner_text="Search loading",
        )
        assert base == moved

    def test_mint_and_resolve_agree_when_aria_label_differs(self):
        """aria-label 与 textContent 不同时，铸造（显式 textVal）与复算（缺省）仍同源。"""
        first, _, explicit = _eval_signature_js(
            tag="button",
            text_content="Search",
            attrs={"aria-label": "Submit search"},
        )
        assert first == explicit


class _CtxDeps:
    run_id = "run-x"


class _Ctx:
    deps = _CtxDeps()


class TestRepeatFindScopeVariant:
    """熔断指纹归一与 scope 变体弱命中。"""

    def test_fingerprint_normalizes_case_and_whitespace(self):
        """大小写 / 空白变体归为同一条指纹。"""
        assert tm._find_fingerprint("  Start ", " Button ", "visible") == tm._find_fingerprint(
            "start", "button", "visible",
        )

    def test_scope_variant_is_repeat(self, monkeypatch):
        """同元素换 scope 重扫 → 判为重复。"""
        monkeypatch.setattr(tm, "_manager", lambda: object())
        monkeypatch.setattr(tm, "_page_key", lambda manager: "page-1")
        monkeypatch.setattr(tm, "_page_url", lambda manager: "https://example.com/a")
        monkeypatch.setattr(tm, "_nav_revision", lambda manager: 3)
        tm._round_finds.clear()
        try:
            tm.record_find(
                _Ctx(),
                page_key="page-1",
                page_url="https://example.com/a",
                nav_rev=3,
                fingerprint=tm._find_fingerprint("Download", "", "container"),
                produced=True,
            )
            assert tm._is_repeat_find(
                _Ctx(), {"text": "Download", "scope": "page", "mode": "elements"},
            )
            assert tm._is_repeat_find(
                _Ctx(), {"text": " download ", "scope": "visible", "mode": "elements"},
            )
            assert not tm._is_repeat_find(
                _Ctx(), {"text": "Other", "scope": "page", "mode": "elements"},
            )
        finally:
            tm._round_finds.clear()
