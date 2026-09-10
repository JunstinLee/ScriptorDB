"""恢复/审批端点无活动 run 时的可读错误文案（阶段一后保留项）。

阶段一把 run 生存期从 SSE 订阅者解耦（断连不 cancel run、不动 registry、
不落盘），原先「断连收敛挂起态」的用例已被推翻删除；此处只保留端点契约：
无活动 run 时返回 404 且 detail 说明当前无活动 run 并给出下一步动作。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from config.app_config import AppConfig
from schemas import ApprovalSubmitRequest

from api.routes import approve as approve_route
from api.routes import browser_interact
from api.routes.browser_interact import (
    TakeoverCancelRequest,
    TakeoverCompleteRequest,
    complete_human_takeover,
)


class _EmptyRegistry:
    def get(self, session_id: str):
        return None

    def remove(self, session_id: str, run_id: str = ""):
        return None


def _patch_empty_registry(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_interact, "get_run_registry", lambda: _EmptyRegistry()
    )
    monkeypatch.setattr(approve_route, "get_run_registry", lambda: _EmptyRegistry())


async def test_recovery_endpoints_report_abandoned_run(monkeypatch):
    """无活动 run 时恢复/审批/取消端点返回可操作的 404 文案。"""
    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(approve_route, "require_workspace", lambda: AppConfig())
    _patch_empty_registry(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await complete_human_takeover(
            TakeoverCompleteRequest(session_id="sess_1", result="x")
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        await browser_interact.cancel_takeover(
            TakeoverCancelRequest(session_id="sess_1")
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        await approve_route.approve(
            "sess_1",
            ApprovalSubmitRequest(request_id="req_1", approved_map={}),
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail
