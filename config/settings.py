from __future__ import annotations

from pathlib import Path

from config.app_config import AppConfig
from config.workspace import (
    WorkspaceSettings,
    WorkspaceRegistry,
    get_last_active_workspace,
    migrate_legacy,
)


Settings = AppConfig


def _persist(config: AppConfig) -> None:
    if not config.workspace_path or not config.workspace_id:
        return
    ws_settings = WorkspaceSettings(
        workspace_id=config.workspace_id,
        name=config.workspace_name or "",
        path=config.workspace_path,
        db_url=config.db_url,
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        default_models=dict(config.default_models),
        auto_restore_sessions=config.auto_restore_sessions,
    )
    ws_settings.save()


def set_default_model(config: AppConfig, provider: str, model: str) -> None:
    config.require_workspace()
    config.default_models[provider] = model
    if config.llm_provider == provider:
        config.llm_model = model
    _persist(config)


def set_provider(config: AppConfig, provider: str) -> None:
    config.require_workspace()
    config.llm_provider = provider
    if provider in config.default_models:
        config.llm_model = config.default_models[provider]
    _persist(config)


def set_auto_restore_sessions(config: AppConfig, value: bool) -> None:
    config.require_workspace()
    config.auto_restore_sessions = value
    _persist(config)


def load_for_workspace(config: AppConfig, workspace_id: str) -> None:
    registry = WorkspaceRegistry()
    rec = registry.get(workspace_id)
    ws_path = Path(rec.path)
    ws_settings = WorkspaceSettings.load(ws_path, rec.id, rec.name)
    config.workspace_id = rec.id
    config.workspace_name = rec.name
    config.workspace_path = ws_path
    config.db_url = ws_settings.db_url
    config.llm_provider = ws_settings.llm_provider
    config.llm_model = ws_settings.llm_model
    config.default_models = dict(ws_settings.default_models)
    config.auto_restore_sessions = ws_settings.auto_restore_sessions


def load_default_workspace() -> bool:
    """在启动时加载默认工作区：自动迁移或读取 last_active。

    返回是否成功加载了一个工作区。
    """
    migrate_legacy()
    rec = get_last_active_workspace()
    if rec is None:
        return False
    load_for_workspace(settings, rec.id)
    return True


settings = AppConfig()
