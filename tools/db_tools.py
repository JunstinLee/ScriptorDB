from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry, RunContext
from sqlalchemy import text

from config.settings import Settings
from schemas.db import ColumnDef
from tools.db_repository import DatabaseRepository
from tools.errors import _to_tool_error
from tools.schema_helpers import (
    extract_where_clause,
    get_pk_columns,
    normalize_params,
    parse_dml_table_name,
    quote_identifier,
)
from tools.tool_decorators import db_tool
from tools.tool_result import ToolResult
from tools.validators import (
    validate_create_table_args,
    validate_python_code,
    validate_sql_ddl,
    validate_sql_dml,
    validate_sql_readonly,
)


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


@db_tool(name="run_python_code", category="write", timeout=35, max_retries=2, requires_approval=True, validator=validate_python_code, sequential=True)
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
            output=f"Code executed successfully: {len(result.stdout)} bytes of output",
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
        message = "Code execution exceeded the 4GB memory limit. Please reduce data size or optimize the code."
    else:
        message = result.stderr.strip() or "Code execution failed"

    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category=category,
            message=message,
        ),
    )


@db_tool(name="create_table", category="write", timeout=15, requires_approval=True, validator=validate_create_table_args)
def create_table(
    ctx: RunContext[Settings],
    table_name: str,
    columns: list[ColumnDef],
    if_not_exists: bool = True,
) -> ToolResult:
    repo = DatabaseRepository(ctx.deps.db_url, ctx.deps.workspace_id or "")
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

        with repo.session() as conn:
            conn.execute(text(sql))

        schema_info = repo.get_single_table_schema(table_name)
        return ToolResult(
            success=True,
            output=f"Table {table_name} created successfully",
            data={
                "table": table_name,
                "columns": schema_info["columns"],
                "create_sql": sql,
            },
        )
    except Exception as e:
        return _to_tool_error(e)


_DDL_PREFIXES = ("CREATE", "ALTER", "DROP", "RENAME", "TRUNCATE", "PRAGMA")


@db_tool(name="execute_ddl", category="write", timeout=15, requires_approval=True, validator=validate_sql_ddl)
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

    repo = DatabaseRepository(ctx.deps.db_url, ctx.deps.workspace_id or "")
    try:
        repo.execute_ddl(sql)
        return ToolResult(
            success=True,
            output="DDL executed successfully",
            data={"sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)


_normalize_params = normalize_params
_parse_dml_table_name = parse_dml_table_name
_get_pk_columns = get_pk_columns
_extract_where_clause = extract_where_clause


def _build_insert_undo(
    conn, sql: str, params: list | dict | None, table_name: str
) -> tuple[int, list[tuple[str, dict]]]:
    named_sql, named_params = _normalize_params(sql, params)
    returning_sql = named_sql.rstrip(";").rstrip() + " RETURNING *"
    try:
        result = conn.execute(text(returning_sql), named_params or {})
    except Exception:
        result = conn.execute(text(named_sql), named_params or {})
        return result.rowcount, []
    rows = result.fetchall()
    columns = list(result.keys())
    if not rows:
        return result.rowcount or 0, []

    pk_cols = _get_pk_columns(conn, table_name)
    if not pk_cols:
        return len(rows), []

    undo_entries: list[tuple[str, dict]] = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        pk_conditions = " AND ".join(
            f'"{col}" = :undo_{col}' for col in pk_cols
        )
        undo_sql = f'DELETE FROM "{table_name}" WHERE {pk_conditions}'
        undo_params = {f"undo_{col}": row_dict[col] for col in pk_cols}
        undo_entries.append((undo_sql, undo_params))

    return len(rows), undo_entries


def _build_update_undo(
    conn, sql: str, params: list | dict | None, table_name: str
) -> tuple[int, list[tuple[str, dict]]]:
    named_sql, named_params = _normalize_params(sql, params)
    where_clause = _extract_where_clause(named_sql)

    select_sql = f'SELECT * FROM "{table_name}" WHERE {where_clause}'
    old_result = conn.execute(text(select_sql), named_params or {})
    old_rows = old_result.fetchall()
    columns = list(old_result.keys())

    result = conn.execute(text(named_sql), named_params or {})
    rows_affected = result.rowcount

    if not old_rows:
        return rows_affected, []

    pk_cols = _get_pk_columns(conn, table_name)
    if not pk_cols:
        return rows_affected, []

    undo_entries: list[tuple[str, dict]] = []
    for row in old_rows:
        row_dict = dict(zip(columns, row))
        set_clauses = [
            f'"{col}" = :undo_{col}'
            for col in columns
            if col not in pk_cols
        ]
        pk_conditions = [
            f'"{col}" = :undo_pk_{col}' for col in pk_cols
        ]
        if not set_clauses or not pk_conditions:
            continue
        undo_sql = (
            f'UPDATE "{table_name}" SET {", ".join(set_clauses)}'
            f' WHERE {" AND ".join(pk_conditions)}'
        )
        undo_params = {
            f"undo_{col}": row_dict[col]
            for col in columns
            if col not in pk_cols
        }
        undo_params.update(
            {f"undo_pk_{col}": row_dict[col] for col in pk_cols}
        )
        undo_entries.append((undo_sql, undo_params))

    return rows_affected, undo_entries


def _build_delete_undo(
    conn, sql: str, params: list | dict | None, table_name: str
) -> tuple[int, list[tuple[str, dict]]]:
    named_sql, named_params = _normalize_params(sql, params)
    where_clause = _extract_where_clause(named_sql)

    select_sql = f'SELECT * FROM "{table_name}" WHERE {where_clause}'
    old_result = conn.execute(text(select_sql), named_params or {})
    old_rows = old_result.fetchall()
    columns = list(old_result.keys())

    result = conn.execute(text(named_sql), named_params or {})
    rows_affected = result.rowcount

    if not old_rows:
        return rows_affected, []

    undo_entries: list[tuple[str, dict]] = []
    for row in old_rows:
        row_dict = dict(zip(columns, row))
        col_list = [f'"{col}"' for col in columns]
        val_placeholders = [f":undo_{col}" for col in columns]
        undo_sql = (
            f'INSERT INTO "{table_name}" ({", ".join(col_list)})'
            f' VALUES ({", ".join(val_placeholders)})'
        )
        undo_params = {f"undo_{col}": row_dict[col] for col in columns}
        undo_entries.append((undo_sql, undo_params))

    return rows_affected, undo_entries


_DML_PREFIXES = ("INSERT", "UPDATE", "DELETE")


@db_tool(name="write_data", category="write", timeout=15, requires_approval=True, validator=validate_sql_dml)
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

    if isinstance(params, list) and params and any(isinstance(p, (list, dict)) for p in params):
        raise ModelRetry(
            "Batch data insertion detected. "
            "When importing bulk data from files (CSV, Excel), "
            "use import_csv_to_db or import_excel_to_db instead of write_data."
        )

    repo = DatabaseRepository(ctx.deps.db_url, ctx.deps.workspace_id or "")
    try:
        with repo.session() as conn:
            table_name = _parse_dml_table_name(sql)

            undo_entries: list[tuple[str, dict]] = []

            if upper.startswith("INSERT") and table_name:
                rows_affected, undo_entries = _build_insert_undo(
                    conn, sql, params, table_name
                )
            elif upper.startswith("UPDATE") and table_name:
                rows_affected, undo_entries = _build_update_undo(
                    conn, sql, params, table_name
                )
            elif upper.startswith("DELETE") and table_name:
                rows_affected, undo_entries = _build_delete_undo(
                    conn, sql, params, table_name
                )
            else:
                result = conn.execute(text(sql), params or {})
                rows_affected = result.rowcount

            undo_manager = getattr(ctx.deps, "undo_manager", None)
            if undo_manager is not None and undo_manager.current_group_id is not None and table_name and undo_entries:
                operation = upper.split()[0]
                for undo_sql, undo_params in undo_entries:
                    undo_manager.record_undo(
                        operation, table_name, undo_sql, undo_params
                    )

        return ToolResult(
            success=True,
            output=f"Data written successfully, {rows_affected} row{'s' if rows_affected != 1 else ''} affected",
            data={"rows_affected": rows_affected, "sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)
