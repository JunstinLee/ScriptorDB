from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnDef(BaseModel):
    name: str
    type: str = "TEXT"
    nullable: bool = True
    default: str | None = None
    pk: bool = False
    references: str | None = Field(
        default=None,
        description="Foreign key reference, e.g. 'other_table(id)'",
    )
