from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from typing import Any

from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from api.dependencies import get_app_context, get_config
from schemas import ApiKeyRequest, ApiKeyStatus, ApiKeyTestResponse
from services.api_key_service import (
    check_api_key_status,
    clear_status_cache,
    test_key,
)

router = APIRouter(tags=["api-keys"])


@router.get("/api/settings/api-key/status", response_model=ApiKeyStatus)
async def api_key_status(provider: str = "", refresh: bool = False):
    """Actively check whether the provider's stored key is usable.

    Always answers 200 with a status field; an unreachable provider is
    reported as ``unknown`` rather than surfacing as a server error.
    """
    config = get_config()
    target = provider or config.llm_provider
    if target not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {target}"
        )
    return await asyncio.to_thread(
        check_api_key_status, target, config.workspace_id, force=refresh
    )


@router.post("/api/settings/api-key", response_model=ApiKeyTestResponse)
async def set_api_key(req: ApiKeyRequest):
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {req.provider}"
        )
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    config = get_config()
    save_api_key(req.provider, req.api_key.strip(), config.workspace_id)
    clear_status_cache()
    get_app_context().invalidate_agent()
    return ApiKeyTestResponse(ok=True)


@router.delete("/api/settings/api-key/{provider}", response_model=ApiKeyTestResponse)
async def delete_provider_key(provider: str):
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {provider}"
        )
    config = get_config()
    try:
        delete_api_key(provider, config.workspace_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    clear_status_cache()
    get_app_context().invalidate_agent()
    return ApiKeyTestResponse(ok=True)


@router.post("/api/settings/api-key/test", response_model=ApiKeyTestResponse)
async def test_api_key(req: ApiKeyRequest):
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {req.provider}"
        )
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    cfg: Any = SUPPORTED_PROVIDERS[req.provider]
    ok, error = test_key(cfg, req.api_key)
    if not ok:
        return ApiKeyTestResponse(ok=False, error=error)
    return ApiKeyTestResponse(ok=True)
