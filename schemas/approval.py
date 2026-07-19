from __future__ import annotations

from pydantic import BaseModel


class ApprovalSubmitRequest(BaseModel):
    request_id: str
    approved_map: dict[str, bool]


class ApprovalSubmitResponse(BaseModel):
    ok: bool
