from __future__ import annotations

from sqlalchemy import text

from tools.schema_helpers import (
    extract_where_clause,
    get_pk_columns,
    normalize_params,
    parse_dml_table_name,
)


def _build_insert_undo(
    conn, sql: str, params: list | dict | None, table_name: str
) -> tuple[int, list[tuple[str, dict]]]:
    named_sql, named_params = normalize_params(sql, params)
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

    pk_cols = get_pk_columns(conn, table_name)
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
    named_sql, named_params = normalize_params(sql, params)
    where_clause = extract_where_clause(named_sql)

    select_sql = f'SELECT * FROM "{table_name}" WHERE {where_clause}'
    old_result = conn.execute(text(select_sql), named_params or {})
    old_rows = old_result.fetchall()
    columns = list(old_result.keys())

    result = conn.execute(text(named_sql), named_params or {})
    rows_affected = result.rowcount

    if not old_rows:
        return rows_affected, []

    pk_cols = get_pk_columns(conn, table_name)
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
    named_sql, named_params = normalize_params(sql, params)
    where_clause = extract_where_clause(named_sql)

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
