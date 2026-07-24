from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from browser import get_manager
from server.dependencies import require_workspace

router = APIRouter(prefix="/api/browser", tags=["browser"])


@router.get("/state")
async def get_browser_state():
    require_workspace()
    manager = get_manager()
    return await manager.get_state()


@router.get("/screenshot")
async def get_browser_screenshot():
    config = require_workspace()

    manager = get_manager()
    state = await manager.get_state()

    if not state["screenshot_available"]:
        raise HTTPException(status_code=404, detail="No screenshot available. Call browser_screenshot first.")

    screenshot_path: str | None = state.get("screenshot_path")
    if not screenshot_path:
        raise HTTPException(status_code=404, detail="Invalid screenshot path")

    file_path = Path(screenshot_path)
    if not file_path.is_absolute():
        workspace_path = config.workspace_path
        if workspace_path is None:
            raise HTTPException(status_code=409, detail="No active workspace")
        file_path = (workspace_path / screenshot_path).resolve()
    else:
        file_path = file_path.resolve()

    workspace_path = config.workspace_path
    if workspace_path is not None:
        try:
            file_path.relative_to(workspace_path.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Forbidden")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Screenshot file not found: {screenshot_path}")

    return StreamingResponse(
        file_path.open("rb"),
        media_type="image/png",
        headers={"Cache-Control": "no-cache"}
    )
