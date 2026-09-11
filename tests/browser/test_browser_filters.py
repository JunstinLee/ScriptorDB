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
    def test_build_js_table_entries(self):
        from tools.browser_tools.filter_detect import _build_js_table_entries

        table = {"index": 1, "selector": '[data-scdb-tableroot="1"]', "label": "JS Table"}
        out = _build_js_table_entries([
            {"name": "Gender", "options": ["male", "female"], "current": "female",
             "capability": {"kind": "set_filter", "field": "gender", "call": "x $value",
                            "value_placeholder": "$value", "table_selector": table["selector"]}},
            {"name": "Name", "capability": {"kind": "set_filter", "field": "name", "call": "y"}},
            "junk",                                   # 非 dict 过滤
            None,
        ], table)
        assert len(out) == 2
        gender = out[0]
        assert gender["type"] == "select"
        assert gender["options"] == ["male", "female"]
        assert gender["current"] == "female"
        assert gender["table"] == table               # 条目携带 table 身份
        assert gender["capability"]["kind"] == "set_filter"
        assert "$value" in gender["capability"]["call"]

    def test_build_js_table_entries_caps_and_fallback(self):
        from tools.browser_tools.filter_detect import _build_js_table_entries

        table = {"index": 0, "selector": '[data-scdb-tableroot="0"]', "label": ""}
        items = [
            {"name": "", "capability": {"kind": "set_filter", "field": f"f{i}", "call": "x"}}
            for i in range(5)
        ]
        out = _build_js_table_entries(items, table, max_filters=2)
        assert len(out) == 2                          # max_filters 截断
        assert out[0]["name"] == "Unnamed filter"     # 空名兜底


class TestApplyFilterOverride:
    @pytest.mark.asyncio
    async def test_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_apply_filter(_ctx(), action="select",
                                                target="Status", value="Active")
        assert "not launched" in result.lower()


