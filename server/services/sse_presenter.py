from __future__ import annotations

from typing import Any

from config.canonical_models import get_canonical_by_slug
from config.models import resolve_canonical_slug
from server.sse_format import sse_done, sse_event


def event_to_sse(event: dict[str, Any], llm_provider: str = "", llm_model: str | None = None) -> str:
    ev_type = event.get("type", "")
    if ev_type == "new_messages":
        return ""
    if ev_type == "metadata":
        return _enrich_metadata_sse(event, llm_provider, llm_model)
    if ev_type == "run_end":
        return sse_event(ev_type, event) + sse_done()
    return sse_event(ev_type, event)


def _enrich_metadata_sse(event: dict[str, Any], llm_provider: str, llm_model: str | None) -> str:
    slug = None
    display_name = None
    if llm_model:
        resolved = resolve_canonical_slug(llm_provider, llm_model)
        if resolved:
            slug = resolved
            c = get_canonical_by_slug(slug)
            if c:
                display_name = c.display_name
    return sse_event(
        "metadata",
        {
            **event,
            "canonical_slug": slug,
            "display_name": display_name,
            "provider_specific_id": llm_model,
        },
    )
