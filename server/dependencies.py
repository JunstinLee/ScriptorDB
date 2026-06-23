from __future__ import annotations

from fastapi import HTTPException

from config.app_config import AppConfig
from config.settings import settings


def get_config() -> AppConfig:
    """当前应用配置单例。后续阶段可改为 AppContext 注入。"""
    return settings


def require_workspace() -> AppConfig:
    config = get_config()
    if not config.workspace_id:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "No active workspace",
                "code": "WORKSPACE_NOT_SELECTED",
            },
        )
    return config
