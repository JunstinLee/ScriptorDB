from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry, RunContext
from sqlalchemy import text

from config.settings import Settings
from tools.db_connection import _get_all_tables, _get_single_table_schema, get_connection
from tools.errors import _to_tool_error
from tools.tool_result import ToolResult
from tools.undo_log import add_entry, create_group


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
    finally:
        conn.close()


def get_schema(ctx: RunContext[Settings], table: str | None = None) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        if table:
            schema_info = _get_single_table_schema(conn, ctx.deps.db_url, table)
            return ToolResult(
                success=True,
                output=f"Table {table}: {len(schema_info['columns'])} column{'s' if len(schema_info['columns']) != 1 else ''}",
                data={"table": table, "columns": schema_info["columns"], "create_sql": schema_info.get("create_sql")},
            )

        tables = _get_all_tables(conn, ctx.deps.db_url)
        return ToolResult(
            success=True,
            output=f"{len(tables)} table{'s' if len(tables) != 1 else ''}",
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
            output=f"Table {table_name} created successfully",
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
            output="DDL executed successfully",
            data={"sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


def _normalize_params(sql: str, params: list | dict | None) -> tuple[str, dict | None]:
    if params is None or isinstance(params, dict):
        return sql, params
    if not isinstance(params, list):
        return sql, params
    named_params: dict[str, Any] = {}
    param_idx = -1

    def _repl(_match: re.Match) -> str:
        nonlocal param_idx
        param_idx += 1
        name = f"p{param_idx}"
        named_params[name] = params[param_idx] if param_idx < len(params) else None
        return f":{name}"

    if sql.count("?") > 0:
        new_sql = re.sub(r"\?", _repl, sql)
    elif "%s" in sql:
        new_sql = re.sub(r"%s", _repl, sql)
    else:
        return sql, None
    return new_sql, named_params


def _parse_dml_table_name(sql: str) -> str | None:
    m = re.match(
        r"(?i)\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"
        r"[\"`]?(\w+)[\"`]?",
        sql.strip(),
    )
    parsed = m.group(2) if m else None
    if m:
        return parsed
    return None


def _get_pk_columns(conn, table: str) -> list[str]:
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(conn)
    pk = insp.get_pk_constraint(table)
    return list(pk.get("constrained_columns", [])) if pk else []


def _extract_where_clause(sql: str) -> str:
    m = re.search(r"(?i)\bWHERE\b\s+(.+)", sql, re.DOTALL)
    if m:
        return m.group(1).rstrip(";").strip()
    return ""


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
        table_name = _parse_dml_table_name(sql)

        undo_entries: list[tuple[str, dict]] = []
        undo_group_id: int | None = None
        undo_seq = 0

        session_id = ctx.deps.chat_session_id
        run_id = ctx.deps.run_id
        prompt = ctx.deps.chat_prompt or ""

        if session_id and table_name:
            undo_group_id = ctx.deps.current_undo_group_id
            if undo_group_id is None:
                undo_group_id = create_group(
                    conn, session_id, run_id, prompt,
                )
                ctx.deps.current_undo_group_id = undo_group_id
            else:
                prev_row = conn.execute(
                    text(
                        "SELECT COALESCE(MAX(seq_in_group), 0) FROM _scriptordb_undo_entries WHERE group_id = :gid"
                    ),
                    {"gid": undo_group_id},
                ).fetchone()
                undo_seq = prev_row[0] if prev_row is not None else 0

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

        if undo_group_id is not None and table_name:
            for i, (undo_sql, undo_params) in enumerate(undo_entries):
                undo_seq += 1
                add_entry(
                    conn,
                    undo_group_id,
                    undo_seq,
                    upper.split()[0],
                    table_name,
                    undo_sql,
                    undo_params,
                )

        conn.commit()
        return ToolResult(
            success=True,
            output=f"Data written successfully, {rows_affected} row{'s' if rows_affected != 1 else ''} affected",
            data={"rows_affected": rows_affected, "sql": sql},
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()
