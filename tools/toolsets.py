from __future__ import annotations

from pydantic_ai import Tool
from pydantic_ai.toolsets.function import FunctionToolset

from tools.data_tools import list_files, read_csv, read_file, write_csv, write_file
from tools.db_tools import get_schema, query_database, run_python_code
from tools.export_tools import export_excel
from tools.validators import validate_file_path, validate_python_code, validate_sql_readonly
from tools.viz_tools import plot_chart


_read_tools = [
    Tool(
        query_database,
        takes_ctx=True,
        name="query_database",
        timeout=10,
        max_retries=2,
        requires_approval=False,
        args_validator=validate_sql_readonly,
        include_return_schema=True,
    ),
    Tool(
        get_schema,
        takes_ctx=True,
        name="get_schema",
        timeout=5,
        max_retries=1,
        requires_approval=False,
        include_return_schema=True,
    ),
    Tool(
        read_csv,
        takes_ctx=True,
        name="read_csv",
        timeout=30,
        max_retries=1,
        requires_approval=False,
        args_validator=validate_file_path,
        include_return_schema=True,
    ),
    Tool(
        read_file,
        takes_ctx=True,
        name="read_file",
        timeout=10,
        max_retries=1,
        requires_approval=False,
        args_validator=validate_file_path,
        include_return_schema=True,
    ),
    Tool(
        list_files,
        takes_ctx=True,
        name="list_files",
        timeout=5,
        max_retries=1,
        requires_approval=False,
        include_return_schema=True,
    ),
]


_write_tools = [
    Tool(
        write_csv,
        takes_ctx=True,
        name="write_csv",
        timeout=30,
        max_retries=1,
        requires_approval=True,
        args_validator=validate_file_path,
        include_return_schema=True,
    ),
    Tool(
        write_file,
        takes_ctx=True,
        name="write_file",
        timeout=10,
        max_retries=1,
        requires_approval=True,
        args_validator=validate_file_path,
        include_return_schema=True,
    ),
    Tool(
        export_excel,
        takes_ctx=True,
        name="export_excel",
        timeout=60,
        max_retries=1,
        requires_approval=True,
        args_validator=validate_file_path,
        include_return_schema=True,
    ),
    Tool(
        run_python_code,
        takes_ctx=True,
        name="run_python_code",
        timeout=35,
        max_retries=2,
        requires_approval=True,
        args_validator=validate_python_code,
        sequential=True,
        include_return_schema=True,
    ),
]


_viz_tools = [
    Tool(
        plot_chart,
        takes_ctx=True,
        name="plot_chart",
        timeout=30,
        max_retries=1,
        requires_approval=False,
        include_return_schema=True,
    ),
]


read_toolset = FunctionToolset(
    instructions=(
        "Read-only database and file operations. "
        "Use query_database, get_schema for database queries; "
        "read_csv, read_file, list_files for file system inspection. "
        "All output is returned as structured ToolResult with success/error/data fields."
    ),
    tools=_read_tools,
)


write_toolset = FunctionToolset(
    instructions=(
        "Write and export operations. ALL operations in this toolset require user approval. "
        "Use write_csv, write_file for file output; "
        "export_excel for .xlsx export; "
        "run_python_code for sandboxed Python execution. "
        "All output is returned as structured ToolResult with success/error/data fields."
    ),
    tools=_write_tools,
)


viz_toolset = FunctionToolset(
    instructions=(
        "Visualization tools. Use plot_chart to generate charts (line, bar, scatter, pie). "
        "Charts are saved as PNG files."
    ),
    tools=_viz_tools,
)
