from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from server.dependencies import require_workspace
from server.schemas import (
    HistoryMatchSegment,
    HistorySearchMatch,
    HistorySearchResponse,
    HistorySearchResultItem,
)
from server.sessions import get_session_store

router = APIRouter(prefix="/api/history", tags=["history"])


def _build_title(content: str) -> str:
    cleaned = content.replace(r"\s+", " ").strip()
    if len(cleaned) > 24:
        return cleaned[:24] + "..."
    return cleaned


def _make_snippet(text: str, query: str) -> HistorySearchMatch | None:
    if not query:
        return None
    lower_text = text.lower()
    lower_query = query.lower()
    idx = lower_text.find(lower_query)
    if idx == -1:
        return None

    start = max(0, idx - 30)
    end = min(len(text), idx + len(query) + 30)

    prefix = text[start:idx]
    match_text = text[idx : idx + len(query)]
    suffix = text[idx + len(query) : end]

    prefix_ellipsis = start > 0
    suffix_ellipsis = end < len(text)

    segments: list[HistoryMatchSegment] = []
    prefix_display = ("…" if prefix_ellipsis else "") + prefix
    if prefix_display:
        segments.append(HistoryMatchSegment(text=prefix_display, highlight=False))
    segments.append(HistoryMatchSegment(text=match_text, highlight=True))
    suffix_display = suffix + ("…" if suffix_ellipsis else "")
    if suffix_display:
        segments.append(HistoryMatchSegment(text=suffix_display, highlight=False))
    return HistorySearchMatch(segments=segments)


def _extract_title(session) -> str | None:
    first_user = next(
        (m for m in session.messages if m.role == "user" and m.content.strip()),
        None,
    )
    if first_user is None:
        return None
    return _build_title(first_user.content)


@router.get("/search", response_model=HistorySearchResponse)
async def search_history(
    q: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    """Search or browse session history with pagination and highlighted snippets."""
    require_workspace()
    store = get_session_store()
    sessions = store.list_sessions()
    query = q.strip()

    results: list[HistorySearchResultItem] = []
    for session in sessions:
        title = _extract_title(session)
        base_item = HistorySearchResultItem(
            session_id=session.session_id,
            title=title,
            created_at=session.created_at,
            last_access=session.last_access,
            message_count=len(session.messages),
        )

        if not query:
            results.append(base_item)
            continue

        match_count = 0
        matches: list[HistorySearchMatch] = []
        for message in session.messages:
            if message.role not in ("user", "assistant"):
                continue
            if query.lower() not in message.content.lower():
                continue
            match_count += 1
            if len(matches) < 2:
                snippet = _make_snippet(message.content, query)
                if snippet is not None:
                    matches.append(snippet)

        if match_count == 0:
            continue

        base_item.match_count = match_count
        base_item.matches = matches
        results.append(base_item)

    total = len(results)
    paginated = results[offset : offset + limit]
    return HistorySearchResponse(
        results=paginated,
        total=total,
        offset=offset,
        limit=limit,
    )
