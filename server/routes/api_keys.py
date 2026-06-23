from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from typing import Any

from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from server.dependencies import get_config
from server.schemas import ApiKeyRequest, ApiKeyTestResponse

router = APIRouter(tags=["api-keys"])


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
    return ApiKeyTestResponse(ok=True)


@router.post("/api/settings/api-key/test", response_model=ApiKeyTestResponse)
async def test_api_key(req: ApiKeyRequest):
    """Test an API key by calling the provider's list-models endpoint."""
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {req.provider}"
        )
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    cfg: Any = SUPPORTED_PROVIDERS[req.provider]
    url = f"{cfg.base_url.rstrip('/')}{cfg.list_models_path}"
    headers = {"Authorization": f"Bearer {req.api_key.strip()}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return ApiKeyTestResponse(ok=False, error=str(e))
    return ApiKeyTestResponse(ok=True)
