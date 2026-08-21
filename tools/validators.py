from __future__ import annotations

import json
import re

from pydantic_ai import ModelRetry, RunContext

from config.settings import Settings
from tools.browser_tools.filter_contract import (
    FILTER_ACTIONS,
    FILTER_MECHANISMS,
    JS_TABLE_CAPABILITY_KINDS,
)


def validate_sql_readonly(ctx: RunContext[Settings], sql: str, *args: object, **kwargs: object) -> None:
    stripped = sql.strip()
    if not stripped:
        return
    upper = stripped.upper()
    if not any(
        upper.startswith(prefix)
        for prefix in ("SELECT", "WITH", "EXPLAIN", "PRAGMA", "DESCRIBE", "SHOW")
    ):
        raise ModelRetry(
            "Only read-only queries (SELECT, WITH, EXPLAIN, PRAGMA, DESCRIBE, SHOW) "
            "are allowed. Use write tools for modifications."
        )


def validate_file_path(ctx: RunContext[Settings], filepath: str, *args: object, **kwargs: object) -> None:
    if not filepath or not filepath.strip():
        raise ModelRetry("File path cannot be empty.")
    if ".." in filepath or filepath.startswith("~") or filepath.startswith("/etc"):
        raise ModelRetry(
            f"File path '{filepath}' is not allowed. "
            "Paths must not contain '..' or start with '~' or '/etc'."
        )


def validate_import_args(
    ctx: RunContext[Settings], filepath: str, table_name: str, *args: object, **kwargs: object
) -> None:
    validate_file_path(ctx, filepath, *args, **kwargs)
    if not table_name or not table_name.strip():
        raise ModelRetry("table_name cannot be empty.")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name.strip()):
        raise ModelRetry(
            f"Invalid table name '{table_name}'. "
            "Table names must start with a letter or underscore and contain only letters, digits, and underscores."
        )


def validate_python_code(ctx: RunContext[Settings], code: str, *args: object, **kwargs: object) -> None:
    if not code or not code.strip():
        raise ModelRetry("Code cannot be empty.")
    lowered = code.lower()
    dangerous = ["os.system", "subprocess", "shutil.rmtree", "__import__", "eval(", "exec("]
    for pattern in dangerous:
        if pattern in lowered:
            raise ModelRetry(
                f"Code contains potentially dangerous pattern '{pattern}'. "
                "This is not allowed in the sandbox."
            )


def validate_create_table_args(
    ctx: RunContext[Settings], table_name: str, columns: list, *args: object, **kwargs: object
) -> None:
    if not table_name or not table_name.strip():
        raise ModelRetry("table_name cannot be empty.")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name.strip()):
        raise ModelRetry(
            f"Invalid table name '{table_name}'. "
            "Table names must start with a letter or underscore and contain only letters, digits, and underscores."
        )
    if not columns or len(columns) == 0:
        raise ModelRetry("columns list cannot be empty. At least one column is required.")
    names = [c.name if hasattr(c, "name") else (c.get("name") if isinstance(c, dict) else None) for c in columns]
    seen = set()
    for n in names:
        if not n:
            raise ModelRetry("Each column must have a non-empty name.")
        if n in seen:
            raise ModelRetry(f"Duplicate column name '{n}'.")
        seen.add(n)


_SQL_DDL_PATTERN = re.compile(
    r"^\s*(CREATE|ALTER|DROP|RENAME|TRUNCATE|PRAGMA)\b", re.IGNORECASE
)

_DANGER_DDL = re.compile(
    r"\bDROP\s+DATABASE\b", re.IGNORECASE
)


def validate_sql_ddl(
    ctx: RunContext[Settings], sql: str, confirm_drop: bool = False, *args: object, **kwargs: object
) -> None:
    if not sql or not sql.strip():
        raise ModelRetry("SQL cannot be empty.")
    if _DANGER_DDL.search(sql):
        raise ModelRetry("DROP DATABASE is not allowed.")
    if not _SQL_DDL_PATTERN.match(sql):
        raise ModelRetry(
            "Only DDL statements are allowed: CREATE, ALTER, DROP, RENAME, TRUNCATE, PRAGMA."
        )


_SQL_DML_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE)\b", re.IGNORECASE
)


def validate_sql_dml(
    ctx: RunContext[Settings], sql: str, *args: object, **kwargs: object
) -> None:
    if not sql or not sql.strip():
        raise ModelRetry("SQL cannot be empty.")
    if not _SQL_DML_PATTERN.match(sql):
        raise ModelRetry(
            "Only DML statements are allowed: INSERT, UPDATE, DELETE."
        )
    upper = sql.strip().upper()
    if upper.startswith("DELETE") or upper.startswith("UPDATE"):
        if "WHERE" not in upper:
            raise ModelRetry(
                f"{upper.split()[0]} statements must include a WHERE clause "
                "to limit the affected rows."
            )


def validate_filter_apply_args(
    ctx: RunContext[Settings],
    action: str,
    target: str,
    value: str = "",
    values: str = "",
    submit: bool = True,
    mechanism: str = "dom_action",
    capability: dict | None = None,
    *args: object,
    **kwargs: object,
) -> None:
    if mechanism not in FILTER_MECHANISMS:
        raise ModelRetry(
            f"mechanism 必须是 {sorted(FILTER_MECHANISMS)} 之一，收到 '{mechanism}'"
        )
    if mechanism == "js_table_api":
        if not isinstance(capability, dict) or not capability:
            raise ModelRetry(
                "mechanism=js_table_api 需要 capability"
                "（browser_detect_filters 返回条目的 capability 字段）"
            )
        kind = capability.get("kind")
        if kind not in JS_TABLE_CAPABILITY_KINDS:
            raise ModelRetry(
                f"capability.kind 必须是 {sorted(JS_TABLE_CAPABILITY_KINDS)} 之一，"
                f"收到 '{kind}'"
            )
    else:
        if action not in FILTER_ACTIONS:
            raise ModelRetry(
                f"action 必须是 {sorted(FILTER_ACTIONS)} 之一，收到 '{action}'"
            )
    if not target or not target.strip():
        raise ModelRetry(
            "target 不能为空（应为 browser_detect_filters 返回的筛选器 name 或 selector）"
        )
    if values and values.strip():
        try:
            parsed = json.loads(values)
        except json.JSONDecodeError:
            raise ModelRetry(
                "values 必须是 JSON 数组字符串，如 '[\"2026-01-01\",\"2026-12-31\"]'"
            )
        if not isinstance(parsed, list):
            raise ModelRetry("values 必须是 JSON 数组字符串")
    if action == "date_range" and not (values and values.strip()):
        raise ModelRetry("date_range 需要 values 提供起止值（JSON 数组字符串）")
