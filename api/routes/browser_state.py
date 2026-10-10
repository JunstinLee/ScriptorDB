from __future__ import annotations

from fastapi import APIRouter

from browser import get_manager
from api.dependencies import require_workspace

router = APIRouter(prefix="/api/browser", tags=["browser"])


@router.get("/state")
async def get_browser_state():
    require_workspace()
    manager = get_manager()
    return await manager.get_state()
