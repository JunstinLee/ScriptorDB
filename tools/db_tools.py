from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry, RunContext
from sqlalchemy import text

from config.settings import Settings
from tools.db_connection import _get_all_tables, _get_single_table_schema, get_connection
from tools.errors import _to_tool_error
from tools.tool_result import ToolResult


class ColumnDef(BaseModel):
    name: str
    type: str = "TEXT"
    nullable: bool = True
    default: str | None = None
    pk: bool = False
    references: str | None = Field(
        default=None,
        description="Foreign key reference, e.g. 'other_table(id)'",
    )


def query_database(ctx: RunContext[Settings], sql: str, limit: int = 100) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        if limit < 1:
            limit = 1
        if limit > 10000:
            limit = 10000
        result = conn.execute(text(sql))
        rows = result.fetchmany(limit + 1)
        columns = list(result.keys())
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
    elif result.memory_killed or "__SANDBOX_MEMORY_LIMIT__" in result.stderr:
        category = ErrorCategory.resource_exhausted
    elif "SyntaxError" in result.stderr or "NameError" in result.stderr:
        category = ErrorCategory.parameter_error

    if category == ErrorCategory.resource_exhausted:
        message = "代码执行时内存超过 4GB 限制，请减少数据量或优化代码"
    else:
        message = result.stderr.strip() or "代码执行失败"

    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category=category,
            message=message,
        ),
    )


def create_table(
    ctx: RunContext[Settings],
    table_name: str,
    columns: list[ColumnDef],
    if_not_exists: bool = True,
) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        cols_sql = []
        foreign_keys = []
        for col in columns:
            parts = [f'"{col.name}"', col.type]
            if col.pk:
                parts.append("PRIMARY KEY")
            elif not col.nullable:
                parts.append("NOT NULL")
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            cols_sql.append(" ".join(parts))
            if col.references:
                foreign_keys.append(
                    f'FOREIGN KEY ("{col.name}") REFERENCES {col.references}'
                )

        all_parts = cols_sql + foreign_keys
        exists_kw = "IF NOT EXISTS " if if_not_exists else ""
        sql = f'CREATE TABLE {exists_kw}"{table_name}" (\n  {", ".join(all_parts)}\n)'
        conn.execute(text(sql))
        conn.commit()

        schema_info = _get_single_table_schema(conn, ctx.deps.db_url, table_name)
        return ToolResult(
            success=True,
            output=f"表 {table_name} 创建成功",
            data={
                "table": table_name,
                "columns": schema_info["columns"],
                "create_sql": sql,
            },
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


_DDL_PREFIXES = ("CREATE", "ALTER", "DROP", "RENAME", "TRUNCATE", "PRAGMA")


def execute_ddl(
    ctx: RunContext[Settings],
    sql: str,
    confirm_drop: bool = False,
) -> ToolResult:
    upper = sql.strip().upper()
    if upper.startswith("DROP") and not confirm_drop:
        raise ModelRetry(
            "DROP operations require confirm_drop=True. "
            "Set confirm_drop to True to confirm you want to drop."
        )

    conn = get_connection(ctx.deps.db_url)
    try:
        conn.execute(text(sql))
        conn.commit()
        return ToolResult(
            success=True,
            output="DDL 执行成功",
            data={"sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


_DML_PREFIXES = ("INSERT", "UPDATE", "DELETE")


def write_data(
    ctx: RunContext[Settings],
    sql: str,
    params: list[Any] | dict[str, Any] | None = None,
) -> ToolResult:
    upper = sql.strip().upper()
    if upper.startswith("DELETE") or upper.startswith("UPDATE"):
        if "WHERE" not in upper:
            raise ModelRetry(
                f"{upper.split()[0]} statements must include a WHERE clause "
                "to limit the affected rows."
            )

    conn = get_connection(ctx.deps.db_url)
    try:
        result = conn.execute(text(sql), params or {})
        conn.commit()
        rows_affected = result.rowcount
        return ToolResult(
            success=True,
            output=f"数据写入成功，影响 {rows_affected} 行",
            data={"rows_affected": rows_affected, "sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()
