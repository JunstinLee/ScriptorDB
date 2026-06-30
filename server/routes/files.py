from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config.workspace import workspace_outputs_dir
from server.dependencies import get_config, require_workspace


router = APIRouter(prefix="/api/files", tags=["files"])


_SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@router.get("/{file_id}")
async def serve_file(file_id: str):
    if not _SAFE_FILE_ID.match(file_id) or ".." in file_id:
        raise HTTPException(status_code=400, detail="Invalid file id")

    config = require_workspace()
    workspace_path = config.workspace_path
    if workspace_path is None:
        raise HTTPException(status_code=409, detail="No active workspace")

    outputs_dir = workspace_outputs_dir(workspace_path).resolve()
    target = (outputs_dir / file_id).resolve()

    try:
        target.relative_to(outputs_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target)
