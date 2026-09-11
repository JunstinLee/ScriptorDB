from __future__ import annotations

import asyncio

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from config.settings import Settings

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


def _ctx(session_id: str | None = None) -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:", chat_session_id=session_id),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


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
# 慢测（真实 Playwright）
# ---------------------------------------------------------------------------

class TestFiltersSlow:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_detect_recognizes_filters(self, tmp_path):
        from tools.browser import browser_detect_filters, browser_launch, browser_navigate

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
        from tools.browser import (
            browser_apply_filter,
            browser_evaluate,
            browser_launch,
            browser_navigate,
        )

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
        from tools.browser import browser_detect_filters, browser_launch, browser_navigate

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
        from unittest.mock import patch

        from browser import get_manager
        from tools.browser import browser_apply_filter, browser_launch, browser_navigate

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
        from tools.browser import browser_detect_filters, browser_launch, browser_navigate

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
        from tools.browser import (
            browser_apply_filter,
            browser_detect_filters,
            browser_evaluate,
            browser_launch,
            browser_navigate,
        )

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
                                         capability=gender["capability"],
                                         table=gender["table"])
        assert "已设置 Gender = female" in res
        n = await browser_evaluate(_ctx(), "document.querySelectorAll('.tabulator-row').length")
        assert int(n) == 2                     # 仅 female 两行（Mary May / Christine Lobowski）
        state = await browser_evaluate(
            _ctx(),
            "JSON.stringify(Tabulator.findTable(document.querySelector('.tabulator'))[0].getFilters())",
        )
        assert "female" in state                # 实例筛选状态已生效（browser_evaluate 返回 JSON 编码串）
