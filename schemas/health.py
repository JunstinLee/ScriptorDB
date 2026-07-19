from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    workspace_id: str | None = None
    workspace_name: str | None = None
