from __future__ import annotations

from typing import Any

from pydantic_ai import ModelRetry, RunContext
from sqlalchemy import text

from config.settings import Settings
from schemas.db import ColumnDef
from database.repository import DatabaseRepository
from tools.db_tools_undo import (
    _build_delete_undo,
    _build_insert_undo,
    _build_update_undo,
)
from tools.errors import _to_tool_error
from tools.schema_helpers import parse_dml_table_name
from tools.tool_decorators import db_tool
from tools.tool_result import ToolResult
from tools.validators import (
    validate_create_table_args,
    validate_sql_ddl,
    validate_sql_dml,
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
            table_name = parse_dml_table_name(sql)

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
