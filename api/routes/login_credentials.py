from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.dependencies import require_workspace
from services import login_credential_service
from schemas.login_credential import (
    CredentialStatusResponse,
    LoginCredentialSpec,
    SiteStatusRequest,
)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _workspace_id(config: object) -> str:
    """require_workspace 已保证非 None；显式收窄以满足类型检查。"""
    wid = getattr(config, "workspace_id", None)
    if not isinstance(wid, str) or not wid:
        raise HTTPException(status_code=409, detail="No active workspace")
    return wid


@router.post("/site-status", response_model=CredentialStatusResponse)
async def site_status(req: SiteStatusRequest) -> CredentialStatusResponse:
    """站点凭证状态查询；200 恒返（configured=false 也是 200，无 404）。"""
    config = require_workspace()
    return login_credential_service.site_status(_workspace_id(config), req)


@router.post("", response_model=CredentialStatusResponse)
async def save_credential(req: LoginCredentialSpec) -> CredentialStatusResponse:
    """保存（幂等覆盖）站点凭证，写入系统密钥；返回非敏感状态。"""
    config = require_workspace()
    try:
        return login_credential_service.save(_workspace_id(config), req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{site}")
async def delete_credential(site: str) -> dict:
    """删除站点凭证；幂等（不存在也返回 ok，无 404）。"""
    config = require_workspace()
    login_credential_service.delete(_workspace_id(config), site)
    return {"ok": True, "site": site}
