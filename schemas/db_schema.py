from __future__ import annotations

from pydantic import BaseModel, Field


class SchemaColumn(BaseModel):
    name: str
    type: str
    pk: bool = False
    notnull: bool = False
    default_value: str | None = None
    autoincrement: bool = False


class SchemaTable(BaseModel):
    name: str
    sql: str
    columns: list[SchemaColumn] = Field(default_factory=list)


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]
