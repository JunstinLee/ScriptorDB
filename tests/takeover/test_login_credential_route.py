"""登录凭证 route：HTTP 语义（无 ASGI，直接调 handler）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import config.credential_store as store
from schemas.login_credential import SiteStatusRequest
from tests.support.credentials import SITE, WS, spec


@pytest.fixture
def route_client(monkeypatch):
    """构造无 ASGI 的 route handler 直接调用环境：mock require_workspace。"""
    from api.routes import login_credentials as route_mod

    monkeypatch.setattr(
        route_mod,
        "require_workspace",
        lambda: type("Cfg", (), {"workspace_id": WS})(),
    )
    return route_mod


async def test_route_site_status(route_client):
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is False

    await route_client.save_credential(spec())
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is True


async def test_route_save_then_status_flip(route_client):
    await route_client.save_credential(spec())
    res = await route_client.site_status(
        SiteStatusRequest(url=f"https://{SITE}/login")
    )
    assert res.configured is True
    assert res.extra_field_label is None


async def test_route_missing_url_400(route_client):
    with pytest.raises(HTTPException) as ei:
        await route_client.save_credential(spec(site=None, url=None))
    assert ei.value.status_code == 400


async def test_route_empty_username_400(route_client):
    with pytest.raises(HTTPException) as ei:
        await route_client.save_credential(spec(username=""))
    assert ei.value.status_code == 400


async def test_route_delete_idempotent(route_client):
    assert await route_client.delete_credential(SITE) == {"ok": True, "site": SITE}
    await route_client.save_credential(spec())
    assert await route_client.delete_credential(SITE) == {"ok": True, "site": SITE}
    assert store.has_site_credential(WS, SITE) is False
