from __future__ import annotations

from pydantic_ai import RunContext
from sqlalchemy import text

from config.settings import Settings
from database.repository import DatabaseRepository
from tools.errors import _to_tool_error
from tools.tool_decorators import db_tool
from tools.tool_result import ToolResult
from tools.validators import validate_sql_readonly


@db_tool(name="query_database", timeout=10, max_retries=2, validator=validate_sql_readonly)
def query_database(ctx: RunContext[Settings], sql: str, limit: int = 100) -> ToolResult:
    repo = DatabaseRepository(ctx.deps.db_url, ctx.deps.workspace_id or "")
    try:
        if limit < 1:
            limit = 1
        if limit > 10000:
            limit = 10000

        with repo.session() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchmany(limit + 1)
            columns = list(result.keys())
            truncated = len(rows) > limit
            if truncated:
                rows = rows[:limit]

        return ToolResult(
            success=True,
            output=f"Query returned {len(rows)} row{'s' if len(rows) != 1 else ''}{' (truncated)' if truncated else ''}, {len(columns)} column{'s' if len(columns) != 1 else ''}",
            data={
                "columns": columns,
                "rows": [[str(v) if v is not None else None for v in row] for row in rows],
                "truncated": truncated,
                "total_returned": len(rows),
            },
        )
    except Exception as e:
        return _to_tool_error(e)


@db_tool(name="get_schema", timeout=5)
def get_schema(ctx: RunContext[Settings], table: str | None = None) -> ToolResult:
    repo = DatabaseRepository(ctx.deps.db_url, ctx.deps.workspace_id or "")
    try:
        if table:
            schema_info = repo.get_single_table_schema(table)
            return ToolResult(
                success=True,
                output=f"Table {table}: {len(schema_info['columns'])} column{'s' if len(schema_info['columns']) != 1 else ''}",
                data={"table": table, "columns": schema_info["columns"], "create_sql": schema_info.get("create_sql")},
            )

        tables = repo.get_all_tables()
        return ToolResult(
            success=True,
            output=f"{len(tables)} table{'s' if len(tables) != 1 else ''}",
            data={"tables": tables},
        )
    except Exception as e:
        return _to_tool_error(e)
