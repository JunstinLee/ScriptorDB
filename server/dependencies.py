from __future__ import annotations

from fastapi import HTTPException

from agents.app_context import AppContext
from config.app_config import AppConfig
from config.settings import settings

_context: AppContext | None = None


def get_config() -> AppConfig:
    """当前应用配置单例。"""
    return settings


def get_app_context() -> AppContext:
    """全局 AppContext 单例：持有配置并缓存按签名复用的 agent。"""
    global _context
    if _context is None:
        _context = AppContext(settings)
    return _context


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
