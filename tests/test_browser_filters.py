from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from browser import get_manager
from config.settings import Settings
from server.filter_confirm import FilterOverride, get_filter_confirm_store
from tools.browser_tools.filters import _RESOLVE_SELECTOR_JS, browser_apply_filter, browser_detect_filters
from tools.validators import validate_filter_apply_args

pytestmark = pytest.mark.usefixtures("cleanup_browser")

_FILTERS_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<form id="filters">
  <label for="status">Status</label>
  <select id="status" name="status">
    <option value="">All</option>
    <option value="active">Active</option>
    <option value="inactive">Inactive</option>
  </select>
  <label for="start">Start</label>
  <input type="date" id="start" name="start">
  <input type="date" id="end" name="end">
  <label for="kw">Keyword</label>
  <input type="text" id="kw" name="kw" placeholder="Search">
  <label><input type="checkbox" name="type" value="pdf" checked> PDF</label>
  <label><input type="checkbox" name="type" value="doc"> DOC</label>
  <input type="range" id="size" name="size" min="0" max="100" value="30">
  <button type="submit" id="apply">Apply</button>
</form>
<div id="result">all items</div>
<script>
  document.getElementById('apply').addEventListener('click', function (e) {
    e.preventDefault();
    var s = document.getElementById('status').value;
    var kw = document.getElementById('kw').value;
    document.getElementById('result').textContent = 'result:' + s + ':' + kw;
  });
</script>
</body></html>"""


def _ctx(session_id: str | None = None) -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:", chat_session_id=session_id),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# 快测（无浏览器）
# ---------------------------------------------------------------------------

class TestFilterApplyValidator:
    @pytest.mark.asyncio
    async def test_validator_cases(self):
        ctx = _ctx()
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "bogus", "x")
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "select", "  ")
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "date_range", "d")
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "select", "d", values="not-json")
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "select", "d", values='"str"')
        # 合法组合不抛错
        validate_filter_apply_args(ctx, "select", "Status", value="Active")
        validate_filter_apply_args(
            ctx, "date_range", "Start", values='["2026-01-01","2026-12-31"]'
        )


class TestFilterConfirmStore:
    def test_override_pop_once(self):
        store = get_filter_confirm_store()
        store.add(FilterOverride(session_id="s1", run_id="r1", request_id="q1",
                                 actions={"action": "select", "target": "Status", "value": "Active"}))
        got = store.pop("s1")
        assert got is not None and got.actions["value"] == "Active"
        assert store.pop("s1") is None  # 一次性


class TestDetectFiltersCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_and_params(self):
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.evaluate = AsyncMock(return_value=[
            {"name": "Status", "type": "select", "selector": "#status", "current": "Active",
             "options": ["Active", "Inactive"], "multiple": False},
            {"name": "", "type": "text", "selector": "input:nth-of-type(2)", "current": ""},
            "junk",  # 非 dict 应被过滤
        ])
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_detect_filters(_ctx())
        assert result["count"] == 2
        assert result["filters"][0]["name"] == "Status"
        assert result["filters"][1]["name"] == "Unnamed filter"  # 空名兜底
        assert result["filters"][1]["fragile"] is True  # nth-of-type 标记
        mock_page.evaluate.assert_awaited_once()
        params = mock_page.evaluate.call_args.args[1]
        assert params["maxFilters"] == 20  # JS 侧截断参数传递

    @pytest.mark.asyncio
    async def test_detect_error(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("boom"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_detect_filters(_ctx())
        assert "failed" in result["error"].lower()


class TestApplyFilterOverride:
    @pytest.mark.asyncio
    async def test_override_replaces_args(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=lambda js, *a: (
            "#status" if js == _RESOLVE_SELECTOR_JS
            else [{"v": "Active", "t": "Active"}, {"v": "Inactive", "t": "Inactive"}]
            if "Array.from(el.options)" in js
            else None
        ))
        mock_page.select_option = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        store = get_filter_confirm_store()
        store.add(FilterOverride(session_id="s1", run_id="r1", request_id="q1",
                                 actions={"action": "select", "target": "Status",
                                          "value": "Inactive", "submit": False}))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_apply_filter(_ctx("s1"), action="select",
                                                target="Status", value="Active")
        assert "Inactive" in result  # 用户改值生效
        mock_page.select_option.assert_awaited_once_with("#status", value="Inactive")

    @pytest.mark.asyncio
    async def test_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_apply_filter(_ctx(), action="select",
                                                target="Status", value="Active")
        assert "not launched" in result.lower()


# ---------------------------------------------------------------------------
# 慢测（真实 Playwright）
# ---------------------------------------------------------------------------

class TestFiltersSlow:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_detect_recognizes_filters(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate

        page_file = tmp_path / "filters.html"
        page_file.write_text(_FILTERS_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())

        result = await browser_detect_filters(_ctx())
        types = [f["type"] for f in result["filters"]]
        by_name = {f["name"]: f for f in result["filters"]}
        assert "select" in types and "text" in types and "checkbox" in types and "slider" in types
        assert by_name["Status"]["options"] == ["All", "Active", "Inactive"]
        assert by_name["Start"]["type"] == "date_range"  # 相邻 date input 配对
        assert len(by_name["Start"]["selectors"]) == 2
        assert by_name["PDF"]["type"] == "checkbox"  # checkbox 组条目以选项命名
        assert by_name["Range"]["current"] == "30"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apply_select_and_submit(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate, browser_evaluate

        page_file = tmp_path / "filters.html"
        page_file.write_text(_FILTERS_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())

        result = await browser_apply_filter(_ctx(), action="select",
                                            target="Status", value="Active", submit=True)
        assert "已设置 Status = Active" in result
        assert "已点击提交按钮" in result
        out = await browser_evaluate(_ctx(), "document.getElementById('result').textContent")
        assert "result:active:" in out  # 结果区已按筛选更新
