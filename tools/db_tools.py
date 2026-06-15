from __future__ import annotations

import sqlite3

from pydantic_ai import RunContext

from config.settings import Settings
from tools.db_connection import _get_all_tables, _get_single_table_schema, get_connection
from tools.errors import _to_tool_error
from tools.tool_result import ToolResult


def query_database(ctx: RunContext[Settings], sql: str, limit: int = 100) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        if limit < 1:
            limit = 1
        if limit > 10000:
            limit = 10000
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchmany(limit + 1)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        truncated = len(rows) > limit
        if truncated:
            rows = rows[:limit]

        return ToolResult(
            success=True,
            output=f"查询返回 {len(rows)} 行{'（已截断）' if truncated else ''}，{len(columns)} 列",
            data={
                "columns": columns,
                "rows": [[str(v) if v is not None else None for v in row] for row in rows],
                "truncated": truncated,
                "total_returned": len(rows),
            },
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


def get_schema(ctx: RunContext[Settings], table: str | None = None) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        if table:
            schema_info = _get_single_table_schema(conn, ctx.deps.db_url, table)
            return ToolResult(
                success=True,
                output=f"表 {table}: {len(schema_info['columns'])} 列",
                data={"table": table, "columns": schema_info["columns"], "create_sql": schema_info.get("create_sql")},
            )

        tables = _get_all_tables(conn, ctx.deps.db_url)
        return ToolResult(
            success=True,
            output=f"{len(tables)} 个表",
            data={"tables": tables},
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


def run_python_code(ctx: RunContext[Settings], code: str) -> ToolResult:
    from tools.sandbox import sandbox_execute

    result = sandbox_execute(
        code=code,
        db_url=ctx.deps.db_url,
        timeout=30,
        max_output_kb=10,
    )

    if result.exit_code == 0:
        return ToolResult(
            success=True,
            output=f"代码执行成功: {len(result.stdout)} bytes 输出",
            data={
                "stdout": result.stdout,
                "execution_time_ms": result.elapsed_ms,
            },
        )

    from tools.errors import ErrorCategory
    from tools.tool_result import ToolErrorInfo

    category = ErrorCategory.internal_error
    if result.exit_code == -1:
        category = ErrorCategory.execution_timeout
    elif "SyntaxError" in result.stderr or "NameError" in result.stderr:
        category = ErrorCategory.parameter_error

    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category=category,
            message=result.stderr.strip() or "代码执行失败",
        ),
    )
