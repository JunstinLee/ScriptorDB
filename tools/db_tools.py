from __future__ import annotations

import sqlite3
from textwrap import dedent

from pydantic_ai import RunContext

from config.settings import Settings


def run_python_code(ctx: RunContext[Settings], code: str) -> str:
    conn = sqlite3.connect(ctx.deps.db_url.replace("sqlite:///", ""))
    try:
        namespace = {"conn": conn, "c": conn.cursor()}
        exec(code, namespace)
        conn.commit()
        return "Code executed successfully."
    except Exception as e:
        conn.rollback()
        return f"Error executing code: {e}"
    finally:
        conn.close()


def get_schema(ctx: RunContext[Settings], table: str | None = None) -> str:
    conn = sqlite3.connect(ctx.deps.db_url.replace("sqlite:///", ""))
    try:
        if table:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            row = cursor.fetchone()
            return row[0] if row else f"Table {table} not found."

        cursor = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = cursor.fetchall()
        return "\n".join(f"{name}:\n  {sql}" for name, sql in rows) or "No tables found."
    finally:
        conn.close()


def query_db(ctx: RunContext[Settings], sql: str) -> str:
    conn = sqlite3.connect(ctx.deps.db_url.replace("sqlite:///", ""))
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        header = " | ".join(cols)
        lines = [header, "-" * len(header)] if header else []
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))
        return "\n".join(lines) if lines else "Query returned no results."
    except Exception as e:
        return f"Query failed: {e}"
    finally:
        conn.close()
