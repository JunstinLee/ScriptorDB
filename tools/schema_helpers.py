from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_pk_columns(conn, table: str) -> list[str]:
    insp = sa_inspect(conn)
    pk = insp.get_pk_constraint(table)
    return list(pk.get("constrained_columns", [])) if pk else []


def parse_dml_table_name(sql: str) -> str | None:
    m = re.match(
        r"(?i)\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"
        r"[\"`]?(\w+)[\"`]?",
        sql.strip(),
    )
    return m.group(2) if m else None


def extract_where_clause(sql: str) -> str:
    m = re.search(r"(?i)\bWHERE\b\s+(.+)", sql, re.DOTALL)
    if m:
        return m.group(1).rstrip(";").strip()
    return ""


def normalize_params(sql: str, params: list | dict | None) -> tuple[str, dict | None]:
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


def table_exists(conn, table_name: str) -> bool:
    return table_name in sa_inspect(conn).get_table_names()


def create_table_from_headers(conn, table_name: str, headers: list[str]) -> str:
    _PK_COLUMN_BASE = "_scriptordb_id"

    pk_name = _PK_COLUMN_BASE
    counter = 1
    while pk_name in headers:
        pk_name = f"{_PK_COLUMN_BASE}_{counter}"
        counter += 1

    if conn.dialect.name == "mysql":
        pk_col = f"{quote_identifier(pk_name)} INT AUTO_INCREMENT PRIMARY KEY"
    else:
        pk_col = f"{quote_identifier(pk_name)} INTEGER PRIMARY KEY AUTOINCREMENT"
    cols_sql = [pk_col] + [f"{quote_identifier(header)} TEXT" for header in headers]
    sql = f"CREATE TABLE {quote_identifier(table_name)} (\n  {',\n  '.join(cols_sql)}\n)"
    conn.execute(text(sql))
    return pk_name


def unique_table_name(conn, base_name: str) -> str:
    counter = 1
    candidate = f"{base_name}_{counter}"
    while table_exists(conn, candidate):
        counter += 1
        candidate = f"{base_name}_{counter}"
    return candidate
