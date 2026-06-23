from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from config.workspace_paths import (
    GLOBAL_CONFIG_DIR,
    LEGACY_CONFIG_FILE,
    LEGACY_SESSIONS_BACKUP_FILE,
    LEGACY_SESSIONS_DIR,
    LEGACY_SESSIONS_FILE,
    REGISTRY_FILE,
    REGISTRY_VERSION,
    WorkspaceNotFoundError,
    workspace_dir,
    workspace_sessions_dir,
)
from config.workspace_registry import (
    REGISTRY_VERSION,
    WorkspaceRecord,
    WorkspaceRegistry,
    WorkspaceRegistryData,
    _new_workspace_id,
)
from config.workspace_settings import WorkspaceSettings


def _read_legacy_config() -> dict:
    if not LEGACY_CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(LEGACY_CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def migrate_legacy(current_dir: Path | None = None) -> WorkspaceRecord | None:
    """首次运行迁移：从全局 config.json / sessions.json 创建第一个工作区。

    返回新建的（默认）工作区记录；若已经迁移过则返回 None。
    """
    if REGISTRY_FILE.exists():
        return None

    cwd = current_dir or Path.cwd()
    legacy = _read_legacy_config()
    llm_provider = legacy.get("llm_provider") or "openai"
    default_models = legacy.get("default_models") or {}
    auto_restore = bool(legacy.get("auto_restore_sessions", True))

    db_path = cwd / "scriptordb.sqlite"
    db_url = f"sqlite:///{db_path}"

    resolved = cwd.resolve(strict=False)
    ws_id = _new_workspace_id()
    rec = WorkspaceRecord(
        id=ws_id,
        name=resolved.name or "default",
        path=str(resolved),
        created_at=datetime.utcnow().isoformat(),
    )
    registry = WorkspaceRegistry(REGISTRY_FILE)
    registry._data = WorkspaceRegistryData(
        version=REGISTRY_VERSION,
        last_active_workspace_id=ws_id,
        workspaces={ws_id: rec},
    )
    registry._save()

    ws_dir = workspace_dir(resolved)
    ws_dir.mkdir(parents=True, exist_ok=True)
    sessions_dst = workspace_sessions_dir(resolved)
    sessions_dst.mkdir(parents=True, exist_ok=True)

    if LEGACY_SESSIONS_DIR.exists():
        try:
            for entry in LEGACY_SESSIONS_DIR.iterdir():
                target = sessions_dst / entry.name
                if entry.is_dir():
                    shutil.copytree(entry, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry, target)
        except OSError:
            pass

    if LEGACY_SESSIONS_FILE.exists():
        try:
            shutil.copy2(LEGACY_SESSIONS_FILE, sessions_dst / "sessions.json")
        except OSError:
            pass
        try:
            LEGACY_SESSIONS_FILE.rename(LEGACY_SESSIONS_BACKUP_FILE)
        except OSError:
            pass

    ws_settings = WorkspaceSettings(
        workspace_id=ws_id,
        name=rec.name,
        path=resolved,
        db_url=db_url,
        llm_provider=llm_provider,
        llm_model=default_models.get(llm_provider),
        default_models=default_models,
        auto_restore_sessions=auto_restore,
    )
    ws_settings.save()
    return rec


def get_last_active_workspace(registry: WorkspaceRegistry | None = None) -> WorkspaceRecord | None:
    reg = registry or WorkspaceRegistry(REGISTRY_FILE)
    wid = reg.last_active_id()
    if wid is None:
        return None
    try:
        rec = reg.get(wid)
    except WorkspaceNotFoundError:
        reg.clear_last_active()
        return None
    if not Path(rec.path).exists():
        return None
    return rec


def activate_workspace(workspace_id: str) -> WorkspaceRecord:
    """统一工作区激活入口：registry lookup + 设为 last_active。

    供 CLI / server / dispatcher 共用，避免重复逻辑。
    """
    registry = WorkspaceRegistry()
    rec = registry.set_last_active(workspace_id)
    return rec
