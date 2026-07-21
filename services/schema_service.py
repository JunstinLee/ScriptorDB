from __future__ import annotations

from server.schemas import SchemaColumn, SchemaResponse, SchemaTable
from tools.db_repository import DatabaseRepository

HIDDEN_TABLES = {"_scriptordb_undo_groups", "_scriptordb_undo_entries"}


def get_schema(db_url: str, workspace_id: str) -> SchemaResponse:
    repo = DatabaseRepository(db_url, workspace_id)
    tables_meta = [
        meta
        for meta in repo.get_all_tables()
        if meta["name"] not in HIDDEN_TABLES
    ]
    tables: list[SchemaTable] = []
    for meta in tables_meta:
        table_name = meta["name"]
        schema_info = repo.get_single_table_schema(table_name)
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
        tables.append(SchemaTable(name=table_name, sql=meta.get("sql") or "", columns=columns))
    return SchemaResponse(tables=tables)
