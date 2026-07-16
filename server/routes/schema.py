from __future__ import annotations

from fastapi import APIRouter

from logging_setup import get_logger
from server.dependencies import get_config, require_workspace
from server.schemas import (
    SchemaColumn,
    SchemaResponse,
    SchemaTable,
)
from tools.db_connection import get_all_tables, get_single_table_schema

logger = get_logger("routes.schema")

router = APIRouter(tags=["schema"])

HIDDEN_TABLES = {"_scriptordb_undo_groups", "_scriptordb_undo_entries"}


@router.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    config = require_workspace()
    logger.info("GET /api/schema workspace=%s db_url=%s", config.workspace_id, config.db_url)
    try:
        tables_meta = [
            meta for meta in get_all_tables(config.db_url, workspace_id=config.workspace_id)
            if meta["name"] not in HIDDEN_TABLES
        ]
        tables: list[SchemaTable] = []
        for meta in tables_meta:
            table_name = meta["name"]
            schema_info = get_single_table_schema(config.db_url, table_name, workspace_id=config.workspace_id)
            columns = [
                SchemaColumn(
                    name=col["name"],
                    type=col["type"],
                    pk=col["pk"],
                    notnull=not col["nullable"],
                    default_value=col.get("default"),
                    autoincrement=col["pk"]
                    and str(col["type"]).upper() in ("INTEGER", "INT", "BIGINT"),
                )
                for col in schema_info["columns"]
            ]
            tables.append(
                SchemaTable(name=table_name, sql=meta.get("sql") or "", columns=columns)
            )
        logger.info("GET /api/schema returned %s tables", len(tables))
        return SchemaResponse(tables=tables)
    except Exception as e:
        logger.error("GET /api/schema failed: %s", e)
        raise
