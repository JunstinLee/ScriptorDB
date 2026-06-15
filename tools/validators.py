from __future__ import annotations

import os

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
