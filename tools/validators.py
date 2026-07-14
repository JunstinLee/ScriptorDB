from __future__ import annotations

import re

from pydantic_ai import ModelRetry, RunContext

from config.settings import Settings


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


_DDL_PREFIXES = ("CREATE", "ALTER", "DROP", "RENAME", "TRUNCATE", "PRAGMA")

_SQL_DDL_PATTERN = re.compile(
    r"^\s*(" + "|".join(_DDL_PREFIXES) + r")\b", re.IGNORECASE
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
            f"Only DDL statements are allowed: {', '.join(_DDL_PREFIXES)}."
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
