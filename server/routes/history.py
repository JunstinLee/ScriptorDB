from __future__ import annotations

from fastapi import APIRouter, Query

from server.dependencies import require_workspace
from server.schemas import HistorySearchResponse
from services.history_service import search_history

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/search", response_model=HistorySearchResponse)
async def search_history_endpoint(
    q: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    require_workspace()
    return search_history(q, offset=offset, limit=limit)
