from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from browser import get_manager
from browser.profiles import (
    delete_profile,
    list_profiles,
    load_profile,
    profile_exists,
    save_current_profile,
)
from config.secrets import (
    BrowserProfileCorruptedError,
    BrowserProfileStorageError,
    BrowserProfileTooLargeError,
)
from server.dependencies import require_workspace

router = APIRouter(prefix="/api/browser/profiles", tags=["browser"])


class SaveProfileRequest(BaseModel):
    name: str


def _check_workspace(config):
    if config.workspace_id is None or config.workspace_path is None:
        raise HTTPException(status_code=409, detail="No active workspace")


def _profile_storage_exception(e: BrowserProfileStorageError, name: str) -> HTTPException:
    if isinstance(e, BrowserProfileTooLargeError):
        return HTTPException(
            status_code=413, detail=f"Browser profile '{name}' is too large to save: {e}"
        )
    if isinstance(e, BrowserProfileCorruptedError):
        return HTTPException(
            status_code=500, detail=f"Browser profile '{name}' data is corrupted: {e}"
        )
    return HTTPException(
        status_code=500, detail=f"Browser profile '{name}' could not be stored: {e}"
    )


@router.get("")
async def get_profiles():
    config = require_workspace()
    _check_workspace(config)
    profiles = list_profiles(config.workspace_path)  # type: ignore[arg-type]
    return {"profiles": profiles}


@router.post("")
async def create_profile(req: SaveProfileRequest):
    config = require_workspace()
    _check_workspace(config)

    manager = get_manager()
    if not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    if profile_exists(req.name, config.workspace_id, config.workspace_path):  # type: ignore[arg-type]
        raise HTTPException(status_code=409, detail=f"Profile '{req.name}' already exists")

    try:
        meta = await save_current_profile(
            manager, req.name, config.workspace_id, config.workspace_path  # type: ignore[arg-type]
        )
    except BrowserProfileStorageError as e:
        raise _profile_storage_exception(e, req.name) from e
    return {
        "ok": True,
        "profile": {
            "name": meta.name,
            "domain": meta.domain,
            "cookie_count": meta.cookie_count,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
        },
    }


@router.delete("/{name}")
async def remove_profile(name: str):
    config = require_workspace()
    _check_workspace(config)
    try:
        deleted = delete_profile(name, config.workspace_id, config.workspace_path)  # type: ignore[arg-type]
    except BrowserProfileStorageError as e:
        raise _profile_storage_exception(e, name) from e
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    return {"ok": True, "name": name}


@router.post("/{name}/load")
async def load_browser_profile(name: str):
    config = require_workspace()
    _check_workspace(config)
    manager = get_manager()
    try:
        success = await load_profile(manager, name, config.workspace_id)  # type: ignore[arg-type]
    except BrowserProfileStorageError as e:
        raise _profile_storage_exception(e, name) from e
    if not success:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    return {"ok": True, "name": name}


@router.put("/{name}")
async def update_profile(name: str):
    config = require_workspace()
    _check_workspace(config)

    manager = get_manager()
    if not manager.is_launched():
        raise HTTPException(status_code=400, detail="Browser not launched")

    if not profile_exists(name, config.workspace_id, config.workspace_path):  # type: ignore[arg-type]
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    try:
        meta = await save_current_profile(
            manager, name, config.workspace_id, config.workspace_path  # type: ignore[arg-type]
        )
    except BrowserProfileStorageError as e:
        raise _profile_storage_exception(e, name) from e
    return {
        "ok": True,
        "profile": {
            "name": meta.name,
            "domain": meta.domain,
            "cookie_count": meta.cookie_count,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
        },
    }
