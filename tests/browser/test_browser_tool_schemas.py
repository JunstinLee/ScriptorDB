"""browser 数据提取类工具的返回 schema 契约（object 结构）。"""

from __future__ import annotations

from tools.tool_decorators import get_all_tool_defs


def test_browser_data_tools_return_object_schema():
    import tools.browser_tools.inspect
    import tools.browser_tools.links
    import tools.browser_tools.table

    object_tools = {
        "browser_extract_table",
        "browser_extract_rows",
        "browser_extract_links",
        "browser_inspect_structure",
    }
    for d in get_all_tool_defs():
        if d.name in object_tools:
            assert d.to_tool().function_schema.return_schema["type"] == "object", d.name
