from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config.workspace import workspace_outputs_dir
from server.dependencies import get_config, require_workspace


router = APIRouter(prefix="/api/files", tags=["files"])


_SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls"}


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


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    config = require_workspace()
    workspace_path = config.workspace_path
    if workspace_path is None:
        raise HTTPException(status_code=409, detail="No active workspace")

    filename = file.filename or "upload"
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(_ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    target_dir = Path(workspace_path).resolve()
    target_path = (target_dir / filename).resolve()
    try:
        target_path.relative_to(target_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        contents = await file.read()
        target_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        await file.close()

    return {"filename": filename, "path": str(target_path)}
