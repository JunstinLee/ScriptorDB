from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FilterOverride:
    """用户通过确认抽屉修改后的最终筛选动作（与 browser_apply_filter 参数同名）。

    actions 字段缺省表示该参数未被修改，消费方（browser_apply_filter）保留原值。
    """

    session_id: str
    run_id: str
    request_id: str
    actions: dict[str, Any]
    created_at: str = field(default_factory=_utc_now_iso)


class FilterConfirmStore:
    """以 session_id 为索引的活动筛选确认 override store。

    同一 session 只能存在一个待消费 override；pop 一次性取出，防止残留
    旧值污染后续 run。
    """

    def __init__(self):
        self._by_session: dict[str, FilterOverride] = {}
        self._lock = threading.Lock()

    def add(self, override: FilterOverride) -> None:
        with self._lock:
            self._by_session[override.session_id] = override

    def get(self, session_id: str) -> FilterOverride | None:
        with self._lock:
            return self._by_session.get(session_id)

    def pop(self, session_id: str) -> FilterOverride | None:
        with self._lock:
            return self._by_session.pop(session_id, None)


_filter_confirm_store = FilterConfirmStore()


def get_filter_confirm_store() -> FilterConfirmStore:
    return _filter_confirm_store
