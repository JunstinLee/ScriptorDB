from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.secrets import SUPPORTED_PROVIDERS, get_api_key
from server.dependencies import get_config, require_workspace
from server.schemas import (
    ApiKeyRequest,
    ApiKeyTestResponse,
    ProviderInfo,
    SettingsResponse,
    SettingsUpdateRequest,
)
from config.settings import (
    set_auto_restore_sessions,
    set_default_model,
    set_provider,
)

router = APIRouter(tags=["settings"])


@router.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    config = get_config()
    providers = [
        ProviderInfo(name=name, base_url=cfg.base_url)
        for name, cfg in SUPPORTED_PROVIDERS.items()
    ]
    providers_with_keys = [
        name for name in SUPPORTED_PROVIDERS.keys()
        if get_api_key(name, config.workspace_id)
    ]
    return SettingsResponse(
        llm_provider=config.llm_provider,
        db_url=config.db_url,
        llm_model=config.llm_model,
        default_models=dict(config.default_models),
        auto_restore_sessions=config.auto_restore_sessions,
        providers=providers,
        providers_with_keys=providers_with_keys,
        workspace_id=config.workspace_id,
    )


@router.post("/api/settings", response_model=SettingsResponse)
async def update_settings(req: SettingsUpdateRequest):
    config = require_workspace()
    if req.llm_provider is not None:
        if req.llm_provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {req.llm_provider}"
            )
        set_provider(config, req.llm_provider)
    if req.default_model is not None:
        provider = req.default_model_provider or config.llm_provider
        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {provider}"
            )
        if not req.default_model:
            if provider in config.default_models:
                del config.default_models[provider]
            if provider == config.llm_provider:
                config.llm_model = None
        else:
            set_default_model(config, provider, req.default_model)
    if req.auto_restore_sessions is not None:
        set_auto_restore_sessions(config, req.auto_restore_sessions)
    return await get_settings()
