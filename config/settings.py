from __future__ import annotations

from pathlib import Path

from config.app_config import AppConfig
from config.global_settings import (
    GlobalSettings,
    apply_global_defaults,
    load_global_settings,
    save_global_settings,
)
from config.workspace import (
    WorkspaceSettings,
    WorkspaceRegistry,
    get_last_active_workspace,
    migrate_legacy,
)
from config.workspace_paths import GLOBAL_SETTINGS_FILE


Settings = AppConfig


def _persist(config: AppConfig) -> None:
    if not config.workspace_path or not config.workspace_id:
        return
    # TODO: 当支持"单个工作区覆盖全局默认"时，llm_provider / llm_model / default_models
    # 应只在 ws_settings.use_global_defaults == False 时写入工作区 settings
    ws_settings = WorkspaceSettings(
        workspace_id=config.workspace_id,
        name=config.workspace_name or "",
        path=config.workspace_path,
        db_url=config.db_url,
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        default_models=dict(config.default_models),
        auto_restore_sessions=config.auto_restore_sessions,
        browser_enabled=config.browser_enabled,
        use_global_defaults=True,
        mysql_host=config.mysql_host,
        mysql_port=config.mysql_port,
        mysql_user=config.mysql_user,
        mysql_db=config.mysql_db,
        mysql_password_set=config.mysql_password_set,
    )
    ws_settings.save()


def set_default_model(config: AppConfig, provider: str, model: str) -> None:
    config.require_workspace()
    gs = load_global_settings()
    gs.llm_provider = provider
    gs.default_models[provider] = model
    gs.llm_model = model
    save_global_settings(gs)

    config.llm_provider = provider
    config.default_models[provider] = model
    config.llm_model = model
    _persist(config)


def set_provider(config: AppConfig, provider: str) -> None:
    config.require_workspace()
    gs = load_global_settings()
    gs.llm_provider = provider
    gs.llm_model = gs.default_models.get(provider)
    save_global_settings(gs)

    config.llm_provider = provider
    config.llm_model = config.default_models.get(provider)
    _persist(config)


def set_auto_restore_sessions(config: AppConfig, value: bool) -> None:
    config.require_workspace()
    config.auto_restore_sessions = value
    _persist(config)


def set_browser_enabled(config: AppConfig, value: bool) -> None:
    config.require_workspace()
    config.browser_enabled = value
    _persist(config)


def load_for_workspace(config: AppConfig, workspace_id: str) -> None:
    registry = WorkspaceRegistry()
    rec = registry.get(workspace_id)
    ws_path = Path(rec.path)
    ws_settings = WorkspaceSettings.load(ws_path, rec.id, rec.name)
    # 首次加载时（global_settings.json 不存在），用当前工作区设置作为全局默认的种子
    if not GLOBAL_SETTINGS_FILE.exists():
        save_global_settings(GlobalSettings(
            llm_provider=ws_settings.llm_provider,
            llm_model=ws_settings.llm_model,
            default_models=dict(ws_settings.default_models),
        ))
    # 应用全局默认覆盖
    # TODO: 当支持"单个工作区覆盖"时，先检查 ws_settings.use_global_defaults
    apply_global_defaults(ws_settings)
    config.workspace_id = rec.id
    config.workspace_name = rec.name
    config.workspace_path = ws_path
    config.db_url = ws_settings.db_url
    config.llm_provider = ws_settings.llm_provider
    config.llm_model = ws_settings.llm_model
    config.default_models = dict(ws_settings.default_models)
    config.auto_restore_sessions = ws_settings.auto_restore_sessions
    config.browser_enabled = ws_settings.browser_enabled
    config.mysql_host = ws_settings.mysql_host
    config.mysql_port = ws_settings.mysql_port
    config.mysql_user = ws_settings.mysql_user
    config.mysql_db = ws_settings.mysql_db
    config.mysql_password_set = ws_settings.mysql_password_set


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


# DEPRECATED: Global singleton retained only for bootstrapping (main.py callback, server/dependencies.py).
# All other modules should receive config via parameter / DI (ctx.obj, Depends(require_workspace), RunContext[Settings]).
settings = AppConfig()
