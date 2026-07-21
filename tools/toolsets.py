from __future__ import annotations

import importlib
import pkgutil

from pydantic_ai.toolsets.function import FunctionToolset

import tools as _tools_pkg

from tools.registry import register_toolset
from tools.tool_decorators import get_all_tool_defs


def _discover_and_import_all_tool_modules() -> None:
    for _, module_name, _ in pkgutil.iter_modules(_tools_pkg.__path__):
        importlib.import_module(f"tools.{module_name}")


_discover_and_import_all_tool_modules()


@register_toolset("read")
def _create_read_toolset():
    tools_list = [d.to_tool() for d in get_all_tool_defs() if d.category == "read"]
    return [
        FunctionToolset(
            instructions=(
                "Read-only database and file operations. "
                "Use query_database, get_schema for database queries; "
                "read_csv, read_excel, read_file, list_files for file system inspection. "
                "All output is returned as structured ToolResult with success/error/data fields."
            ),
            tools=tools_list,
        )
    ]


@register_toolset("write")
def _create_write_toolset():
    tools_list = [d.to_tool() for d in get_all_tool_defs() if d.category == "write"]
    return [
        FunctionToolset(
            instructions=(
                "Write and export operations. ALL operations in this toolset require user approval. "
                "Use write_csv, write_file for file output; "
                "export_excel for .xlsx export; "
                "import_csv_to_db and import_excel_to_db to load files into the database; "
                "run_python_code for sandboxed Python execution; "
                "create_table to build a table with structured column definitions; "
                "execute_ddl for generic DDL statements (CREATE/ALTER/DROP); "
                "write_data for parameterized INSERT/UPDATE/DELETE. "
                "DELETE and UPDATE must include a WHERE clause. DROP requires confirm_drop=True. "
                "All output is returned as structured ToolResult with success/error/data fields."
            ),
            tools=tools_list,
        )
    ]


@register_toolset("viz")
def _create_viz_toolset():
    tools_list = [d.to_tool() for d in get_all_tool_defs() if d.category == "viz"]
    return [
        FunctionToolset(
            instructions=(
                "Visualization tools. Use plot_chart to generate charts (line, bar, scatter, pie). "
                "Charts are saved as PNG files."
            ),
            tools=tools_list,
        )
    ]


@register_toolset("crawl")
def _create_crawl_toolset():
    tools_list = [d.to_tool() for d in get_all_tool_defs() if d.category == "crawl"]
    return [
        FunctionToolset(
            instructions=(
                "Web crawling tools. Use crawl_webpage to fetch and extract "
                "content from web pages as Markdown text. "
                "Useful for reading documentation, articles, or any web content "
                "relevant to the user's request."
            ),
            tools=tools_list,
        )
    ]
