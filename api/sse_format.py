from __future__ import annotations

import json as json_mod


def sse_encode_json(obj: dict) -> str:
    return json_mod.dumps(obj, ensure_ascii=False, default=str)


def sse_event(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {sse_encode_json(payload)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"
