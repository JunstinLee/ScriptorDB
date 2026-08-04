from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from browser import get_manager
from server.dependencies import require_workspace

router = APIRouter(prefix="/api/browser", tags=["browser"])


class CookieSetRequest(BaseModel):
    name: str
    value: str
    domain: str | None = None
    path: str | None = "/"
    secure: bool | None = None
    http_only: bool | None = None
    same_site: str | None = None
    expires: int | None = None


def _cookie_info(c: Any) -> dict[str, Any]:
    return {
        "name": c.get("name", ""),
        "domain": c.get("domain", ""),
        "path": c.get("path", ""),
        "expires": c.get("expires"),
        "http_only": c.get("httpOnly", False) or c.get("http_only", False),
        "secure": c.get("secure", False),
        "same_site": c.get("sameSite", "Lax"),
    }


@router.get("/cookies")
async def get_cookies():
    require_workspace()
    manager = get_manager()
    page = manager.page()
    if not page or not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    cookies = await page.context.cookies()
    current_url = page.url

    return {
        "cookies": [_cookie_info(c) for c in cookies],
        "count": len(cookies),
        "current_url": current_url,
    }


@router.post("/cookies")
async def set_cookie(req: CookieSetRequest):
    require_workspace()
    manager = get_manager()
    page = manager.page()
    if not page or not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    cookie_params: dict[str, Any] = {
        "name": req.name,
        "value": req.value,
        "path": req.path or "/",
    }
    if req.domain:
        cookie_params["domain"] = req.domain
    if req.secure is not None:
        cookie_params["secure"] = req.secure
    if req.http_only is not None:
        cookie_params["httpOnly"] = req.http_only
    if req.same_site:
        cookie_params["sameSite"] = req.same_site
    if req.expires is not None:
        cookie_params["expires"] = req.expires

    await page.context.add_cookies([cookie_params])  # type: ignore[arg-type]
    cookie_info = _cookie_info(cookie_params)
    return {"ok": True, "cookie": cookie_info}


@router.delete("/cookies")
async def clear_cookies():
    require_workspace()
    manager = get_manager()
    page = manager.page()
    if not page or not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    raw_cookies = await page.context.cookies()
    count = len(raw_cookies)
    await page.context.clear_cookies()
    return {"ok": True, "cleared": count}


@router.delete("/cookies/{name}")
async def delete_cookie(name: str):
    require_workspace()
    manager = get_manager()
    page = manager.page()
    if not page or not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    raw_cookies = await page.context.cookies()
    matching = [c for c in raw_cookies if c.get("name") == name]
    if not matching:
        raise HTTPException(status_code=404, detail=f"Cookie '{name}' not found")

    await page.context.clear_cookies(name=name)
    return {"ok": True, "name": name}
