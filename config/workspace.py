from __future__ import annotations

from config.workspace_loader import (
    activate_workspace,
    get_last_active_workspace,
    migrate_legacy,
)
from config.workspace_paths import (
    DEFAULT_WORKSPACES_DIR,
    GLOBAL_CONFIG_DIR,
    LEGACY_CONFIG_FILE,
    LEGACY_SESSIONS_BACKUP_FILE,
    LEGACY_SESSIONS_DIR,
    LEGACY_SESSIONS_FILE,
    REGISTRY_FILE,
    REGISTRY_VERSION,
    WorkspaceAlreadyExistsError,
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceNotSelectedError,
    workspace_dir,
    workspace_sessions_dir,
    workspace_settings_file,
)
from config.workspace_registry import (
    REGISTRY_VERSION,
    WorkspaceRecord,
    WorkspaceRegistry,
    WorkspaceRegistryData,
)
from config.workspace_settings import WorkspaceSettings


__all__ = [
    "DEFAULT_WORKSPACES_DIR",
    "GLOBAL_CONFIG_DIR",
    "LEGACY_CONFIG_FILE",
    "LEGACY_SESSIONS_BACKUP_FILE",
    "LEGACY_SESSIONS_DIR",
    "LEGACY_SESSIONS_FILE",
    "REGISTRY_FILE",
    "REGISTRY_VERSION",
    "WorkspaceAlreadyExistsError",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "WorkspaceNotSelectedError",
    "WorkspaceRecord",
    "WorkspaceRegistry",
    "WorkspaceRegistryData",
    "WorkspaceSettings",
    "activate_workspace",
    "get_last_active_workspace",
    "migrate_legacy",
    "workspace_dir",
    "workspace_sessions_dir",
    "workspace_settings_file",
]
