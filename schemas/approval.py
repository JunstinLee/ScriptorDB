from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApprovalSubmitRequest(BaseModel):
    request_id: str
    approved_map: dict[str, bool]
    # 可选：call_id -> 用户修改后的最终参数（仅含被改字段），未提供时原样执行。
    override_args: dict[str, dict[str, Any]] = {}


class ApprovalSubmitResponse(BaseModel):
    ok: bool
