from __future__ import annotations

from pathlib import Path


class WorkspaceError(Exception):
    """工作区相关异常的基类。"""


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspaceAlreadyExistsError(WorkspaceError):
    pass


class WorkspaceNotSelectedError(WorkspaceError):
    pass


GLOBAL_CONFIG_DIR = Path.home() / ".config" / "scriptordb"
DEFAULT_WORKSPACES_DIR = GLOBAL_CONFIG_DIR / "workspaces"
REGISTRY_FILE = GLOBAL_CONFIG_DIR / "workspaces.json"
LEGACY_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"
LEGACY_SESSIONS_DIR = GLOBAL_CONFIG_DIR / "sessions"
LEGACY_SESSIONS_FILE = GLOBAL_CONFIG_DIR / "sessions.json"
LEGACY_SESSIONS_BACKUP_FILE = GLOBAL_CONFIG_DIR / "sessions.json.bak"

REGISTRY_VERSION = 1


def workspace_dir(workspace_path: Path) -> Path:
    return workspace_path / ".scriptordb"


def workspace_settings_file(workspace_path: Path) -> Path:
    return workspace_dir(workspace_path) / "settings.json"


def workspace_sessions_dir(workspace_path: Path) -> Path:
    return workspace_dir(workspace_path) / "sessions"
