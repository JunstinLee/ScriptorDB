from __future__ import annotations

from fastapi import APIRouter

from config.settings import settings
from server.dependencies import get_config
from server.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health():
    config = get_config()
    try:
        model = config.resolved_model if config.workspace_id else (
            config.llm_model or "(not configured)"
        )
    except Exception:
        model = config.llm_model or "(not configured)"
    return HealthResponse(
        status="ok",
        provider=config.llm_provider,
        model=model,
        workspace_id=config.workspace_id,
        workspace_name=config.workspace_name,
    )
