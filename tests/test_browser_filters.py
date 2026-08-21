from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from browser import get_manager
from config.settings import Settings
from tools.browser_tools.filter_apply import browser_apply_filter
from tools.browser_tools.filter_detect import browser_detect_filters
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

_TABULATOR_HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3.0/dist/css/tabulator.min.css">
</head><body>
<div id="table"></div>
<script src="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3.0/dist/js/tabulator.min.js"></script>
<script>
  var rows = [
    {name: "Mary May", gender: "female", rating: 2},
    {name: "Oli Bob", gender: "male", rating: 5},
    {name: "Christine Lobowski", gender: "female", rating: 0},
    {name: "Frank Harbours", gender: "male", rating: 4},
  ];
  new Tabulator("#table", {
    data: rows,
    columns: [
      {title: "Name", field: "name", width: 200},
      {title: "Gender", field: "gender"},
      {title: "Rating", field: "rating"},
    ],
  });
</script>
</body></html>"""


def _ctx(session_id: str | None = None) -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:", chat_session_id=session_id),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


async def _wait_tabulator_rows(count: int) -> None:
    """轮询等待 Tabulator 渲染出 count 行（CDN 加载 + 初始化是异步的）。"""
    from tools.browser import browser_evaluate

    for _ in range(40):
        try:
            n = await browser_evaluate(
                _ctx(), "document.querySelectorAll('.tabulator-row').length"
            )
            if int(n or 0) >= count:
                return
        except Exception:
            pass
        await asyncio.sleep(0.25)


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
        validate_filter_apply_args(ctx, "select", "Status", value="Active", mechanism="ui_event")
        validate_filter_apply_args(
            ctx, "select", "Gender", mechanism="js_table_api",
            capability={"kind": "set_filter", "field": "gender", "call": "x",
                        "value_placeholder": "$value"},
        )
        # mechanism 分支非法组合
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "select", "Status", mechanism="bogus")
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(ctx, "select", "Gender", mechanism="js_table_api")  # 缺 capability
        with pytest.raises(ModelRetry):
            validate_filter_apply_args(
                ctx, "select", "Gender", mechanism="js_table_api",
                capability={"kind": "unknown"},  # kind 不在白名单
            )


class TestDetectFiltersCleanup:
    @staticmethod
    def _item(**over):
        base = {"tag": "input", "type": "text", "nameAttr": "", "ariaLabel": "", "labelText": "",
                "prev": "", "placeholder": "", "text": "", "visible": True, "disabled": False,
                "value": "", "checked": False, "multiple": False, "min": "", "max": "", "step": "",
                "pressed": None, "options": None, "parentKey": ""}
        base.update(over)
        return base

    def test_build_filters_filters_junk_and_caps(self):
        from tools.browser_tools.filter_detect import _build_filters

        items = [
            self._item(_kind="combobox", tag="select", labelText="Status", value="Active",
                       options=["Active", "Inactive"], parentKey="form#f"),
            self._item(_kind="textbox", placeholder="Search", parentKey="form#f"),
            "junk",   # 非 dict 应被过滤
            None,     # 非 dict 应被过滤
        ]
        out = _build_filters(items, max_filters=1)
        assert len(out) == 1                      # max_filters 截断
        assert out[0]["name"] == "Status"

    def test_build_filters_unnamed_fallback(self):
        from tools.browser_tools.filter_detect import _build_filters

        out = _build_filters(
            [self._item(_kind="combobox", tag="select", parentKey="form#f")],
            max_filters=20,
        )
        assert out[0]["name"] == "Unnamed filter"  # 空名兜底

    def test_build_filters_pairs_adjacent_dates(self):
        from tools.browser_tools.filter_detect import _build_filters

        items = [
            self._item(_kind="textbox", type="date", nameAttr="start", labelText="Start",
                       parentKey="form#f", value="2026-01-01"),
            self._item(_kind="textbox", type="date", nameAttr="end", labelText="End",
                       parentKey="form#f", value="2026-12-31"),
        ]
        out = _build_filters(items, max_filters=20)
        assert len(out) == 1                      # 相邻同父 date input 配对
        assert out[0]["type"] == "date_range"
        assert out[0]["name"] == "Start"
        assert out[0]["current"] == ["2026-01-01", "2026-12-31"]

    def test_build_filters_single_date_not_paired(self):
        from tools.browser_tools.filter_detect import _build_filters

        out = _build_filters(
            [self._item(_kind="textbox", type="date", nameAttr="only", labelText="Due",
                        parentKey="form#f")],
            max_filters=20,
        )
        assert len(out) == 1
        assert out[0]["type"] == "date"           # 无相邻 date 时保持单条

    @pytest.mark.asyncio
    async def test_detect_error(self):
        mock_page = AsyncMock()
        mock_page.get_by_role = Mock(side_effect=Exception("boom"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_detect_filters(_ctx())
        assert "failed" in result["error"].lower()


class TestFilterContract:
    def test_is_filter_failure(self):
        from tools.browser_tools.filter_contract import is_filter_failure

        assert is_filter_failure("失败: 未找到筛选器 'x'")
        assert is_filter_failure("failed: timeout")
        assert is_filter_failure("Failed: something")     # 大小写不敏感
        assert not is_filter_failure("已设置 Status = Active")
        assert not is_filter_failure("已点击提交按钮")

    def test_contract_enums(self):
        from tools.browser_tools.filter_contract import (
            FILTER_ACTIONS,
            FILTER_MECHANISMS,
            JS_TABLE_CAPABILITY_KINDS,
        )

        assert set(FILTER_ACTIONS) == {"select", "input", "toggle", "set_range", "date_range"}
        assert "dom_action" in FILTER_MECHANISMS
        assert "js_table_api" in FILTER_MECHANISMS
        assert "set_filter" in JS_TABLE_CAPABILITY_KINDS


class TestDetectJsTableBuilder:
    def test_build_tabulator_filters_entries(self):
        from tools.browser_tools.filter_detect import _build_tabulator_filters

        out = _build_tabulator_filters([
            {"name": "Gender", "field": "gender", "options": ["male", "female"], "current": "female"},
            {"name": "Name", "field": "name"},
            "junk",                                   # 非 dict 过滤
            None,
        ])
        assert len(out) == 2
        gender = out[0]
        assert gender["type"] == "select"
        assert gender["options"] == ["male", "female"]
        assert gender["current"] == "female"
        assert gender["capability"]["kind"] == "set_filter"
        assert gender["capability"]["field"] == "gender"
        assert "$value" in gender["capability"]["call"]
        assert "gender" in gender["capability"]["call"]  # 探测端模板已嵌入列字段

    def test_build_tabulator_filters_caps_and_fallback(self):
        from tools.browser_tools.filter_detect import _build_tabulator_filters

        items = [{"field": f"f{i}", "name": ""} for i in range(5)]
        out = _build_tabulator_filters(items, max_filters=2)
        assert len(out) == 2                          # max_filters 截断
        assert out[0]["name"] == "Unnamed filter"     # 空名兜底


class TestApplyFilterOverride:
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
        assert len(by_name["Start"]["current"]) == 2
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

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_date_pairing(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate

        page_file = tmp_path / "filters.html"
        page_file.write_text(_FILTERS_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())

        result = await browser_detect_filters(_ctx())
        by_name = {f["name"]: f for f in result["filters"]}
        start = by_name["Start"]
        assert start["type"] == "date_range"
        assert len(start["current"]) == 2          # 合并为 date_range 且保留两个输入值
        assert "End" not in by_name                # 相邻配对后不再有独立 End 条目

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apply_failure_records_failure(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate

        page_file = tmp_path / "filters.html"
        page_file.write_text(_FILTERS_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())

        with patch.object(get_manager(), "record_element_failure") as rec:
            result = await browser_apply_filter(_ctx(), action="select",
                                                target="不存在的筛选器", value="x", submit=False)
        assert "失败" in result                     # 返回失败信息
        rec.assert_called_once()                   # 元素失败被记录（触发接管检测）

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_detect_tabulator_js_table(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate

        page_file = tmp_path / "tabulator.html"
        page_file.write_text(_TABULATOR_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())
        await _wait_tabulator_rows(4)

        result = await browser_detect_filters(_ctx())
        js = [f for f in result["filters"] if f.get("source") == "js_table"]
        assert js, f"未识别 JS 表格筛选能力: {result}"
        by_name = {f["name"]: f for f in js}
        entry = by_name.get("Gender")
        assert entry, list(by_name)
        assert entry["mechanism"] == "js_table_api"
        assert entry["capability"]["kind"] == "set_filter"
        assert "$value" in entry["capability"]["call"]
        assert "Name" in by_name and "Rating" in by_name  # 无 headerFilter 的列也有 API 筛选能力

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apply_tabulator_js_table_api(self, tmp_path):
        from tools.browser import browser_launch, browser_navigate, browser_evaluate

        page_file = tmp_path / "tabulator.html"
        page_file.write_text(_TABULATOR_HTML, encoding="utf-8")
        assert "launched successfully" in (await browser_launch(_ctx())).lower()
        await browser_navigate(_ctx(), page_file.as_uri())
        await _wait_tabulator_rows(4)

        result = await browser_detect_filters(_ctx())
        gender = next(f for f in result["filters"]
                      if f.get("source") == "js_table" and f["name"] == "Gender")
        res = await browser_apply_filter(_ctx(), action="select", target="Gender",
                                         value="female", submit=False,
                                         mechanism="js_table_api",
                                         capability=gender["capability"])
        assert "已设置 Gender = female" in res
        n = await browser_evaluate(_ctx(), "document.querySelectorAll('.tabulator-row').length")
        assert int(n) == 2                     # 仅 female 两行（Mary May / Christine Lobowski）
        state = await browser_evaluate(
            _ctx(),
            "JSON.stringify(Tabulator.findTable(document.querySelector('.tabulator'))[0].getFilters())",
        )
        assert '"female"' in state             # 实例筛选状态已生效
