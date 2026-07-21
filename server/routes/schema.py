from __future__ import annotations

from fastapi import APIRouter

from logging_setup import get_logger
from server.dependencies import require_workspace
from server.schemas import SchemaResponse
from services.schema_service import get_schema as svc_get_schema

logger = get_logger("routes.schema")

router = APIRouter(tags=["schema"])


@router.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    config = require_workspace()
    logger.info("GET /api/schema workspace=%s db_url=%s", config.workspace_id, config.db_url)
    try:
        result = svc_get_schema(config.db_url, config.workspace_id)
        logger.info("GET /api/schema returned %s tables", len(result.tables))
        return result
    except Exception as e:
        logger.error("GET /api/schema failed: %s", e)
        raise
