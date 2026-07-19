from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HistoryMatchSegment(BaseModel):
    text: str
    highlight: bool = False


class HistorySearchMatch(BaseModel):
    segments: list[HistoryMatchSegment]


class HistorySearchResultItem(BaseModel):
    session_id: str
    title: str | None = None
    created_at: datetime
    last_access: datetime
    message_count: int
    match_count: int = 0
    matches: list[HistorySearchMatch] = []


class HistorySearchResponse(BaseModel):
    results: list[HistorySearchResultItem]
    total: int
    offset: int
    limit: int
