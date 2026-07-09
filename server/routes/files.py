from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config.workspace import workspace_outputs_dir
from logging_setup import get_logger
from server.dependencies import get_config, require_workspace


router = APIRouter(prefix="/api/files", tags=["files"])
_log = get_logger("server.routes.files")


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
    _log.info("upload received: filename=%s content_type=%s", filename, file.content_type)
    if ".." in filename or "/" in filename or "\\" in filename:
        _log.warning("upload rejected: invalid filename=%s", filename)
        raise HTTPException(status_code=400, detail="Invalid filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_EXTENSIONS:
        _log.warning(
            "upload rejected: unsupported extension=%s filename=%s", suffix, filename
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(_ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    target_dir = Path(workspace_path).resolve()
    target_path = (target_dir / filename).resolve()
    try:
        target_path.relative_to(target_dir)
    except ValueError:
        _log.warning("upload rejected: path traversal attempt filename=%s", filename)
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        contents = await file.read()
        target_path.write_bytes(contents)
    except Exception as e:
        _log.exception("upload failed: filename=%s error=%s", filename, e)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        await file.close()

    _log.info(
        "upload saved: filename=%s path=%s bytes=%d",
        filename,
        target_path,
        len(contents),
    )
    return {"filename": filename, "path": str(target_path)}
