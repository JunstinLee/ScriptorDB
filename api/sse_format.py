from __future__ import annotations

import json as json_mod


def sse_encode_json(obj: dict) -> str:
    return json_mod.dumps(obj, ensure_ascii=False, default=str)


def sse_event(event_name: str, payload: dict, event_id: int | None = None) -> str:
    """编码一个 SSE 帧；event_id 非空时附带 `id:` 行供前端记录游标。

    当前服务端不读取 `Last-Event-ID`（重挂游标只走 `from_index` 查询参数），
    `id:` 行仅为前端记录 lastEventId 保留。
    """
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}event: {event_name}\ndata: {sse_encode_json(payload)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"
