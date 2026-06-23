from __future__ import annotations

from fastapi import APIRouter

from server.dependencies import get_config, require_workspace
from server.schemas import (
    SchemaColumn,
    SchemaResponse,
    SchemaTable,
)
from tools.db_connection import get_all_tables, get_connection

router = APIRouter(tags=["schema"])


@router.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    config = require_workspace()
    db_path = config.db_url.replace("sqlite:///", "")
    conn = get_connection(db_path)
    try:
        tables_meta = get_all_tables(config.db_url)
        tables: list[SchemaTable] = []
        for meta in tables_meta:
            table_name = meta["name"]
            col_cursor = conn.execute(
                f"PRAGMA table_info('{table_name.replace(chr(39), chr(39)+chr(39))}')"
            )
            col_rows = col_cursor.fetchall()
            columns = [
                SchemaColumn(
                    name=col["name"],
                    type=col["type"],
                    pk=bool(col["pk"]),
                    notnull=bool(col["notnull"]),
                    default_value=col["dflt_value"],
                    autoincrement=bool(col["pk"])
                    and col["type"].upper() in ("INTEGER", "INT", "BIGINT"),
                )
                for col in col_rows
            ]
            tables.append(
                SchemaTable(name=table_name, sql=meta["sql"], columns=columns)
            )
    finally:
        conn.close()
    return SchemaResponse(tables=tables)
