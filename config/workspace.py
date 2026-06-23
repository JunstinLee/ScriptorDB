from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


class WorkspaceError(Exception):
    """工作区相关异常的基类。"""


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspaceAlreadyExistsError(WorkspaceError):
    pass


class WorkspaceNotSelectedError(WorkspaceError):
    pass


GLOBAL_CONFIG_DIR = Path.home() / ".config" / "scriptordb"
REGISTRY_FILE = GLOBAL_CONFIG_DIR / "workspaces.json"
LEGACY_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"
LEGACY_SESSIONS_DIR = GLOBAL_CONFIG_DIR / "sessions"
LEGACY_SESSIONS_FILE = GLOBAL_CONFIG_DIR / "sessions.json"
LEGACY_SESSIONS_BACKUP_FILE = GLOBAL_CONFIG_DIR / "sessions.json.bak"

REGISTRY_VERSION = 1


def _new_workspace_id() -> str:
    return f"ws_{uuid.uuid4().hex[:10]}"


@dataclass
class WorkspaceRecord:
    id: str
    name: str
    path: str
    created_at: str


@dataclass
class WorkspaceRegistryData:
    version: int = REGISTRY_VERSION
    last_active_workspace_id: Optional[str] = None
    workspaces: dict[str, WorkspaceRecord] = field(default_factory=dict)


def _load_registry_file() -> WorkspaceRegistryData:
    if not REGISTRY_FILE.exists():
        return WorkspaceRegistryData()
    try:
        payload = json.loads(REGISTRY_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return WorkspaceRegistryData()
    if not isinstance(payload, dict):
        return WorkspaceRegistryData()
    raw_workspaces = payload.get("workspaces", {})
    workspaces: dict[str, WorkspaceRecord] = {}
    if isinstance(raw_workspaces, dict):
        for wid, raw in raw_workspaces.items():
            if not isinstance(raw, dict):
                continue
            try:
                workspaces[str(wid)] = WorkspaceRecord(
                    id=str(raw.get("id") or wid),
                    name=str(raw.get("name") or wid),
                    path=str(raw.get("path") or ""),
                    created_at=str(raw.get("created_at") or ""),
                )
            except Exception:
                continue
    return WorkspaceRegistryData(
        version=int(payload.get("version", REGISTRY_VERSION)),
        last_active_workspace_id=payload.get("last_active_workspace_id"),
        workspaces=workspaces,
    )


def _save_registry_file(data: WorkspaceRegistryData) -> None:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": data.version,
        "last_active_workspace_id": data.last_active_workspace_id,
        "workspaces": {
            wid: asdict(rec) for wid, rec in data.workspaces.items()
        },
    }
    try:
        REGISTRY_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except OSError:
        pass


def workspace_dir(workspace_path: Path) -> Path:
    return workspace_path / ".scriptordb"


def workspace_settings_file(workspace_path: Path) -> Path:
    return workspace_dir(workspace_path) / "settings.json"


def workspace_sessions_dir(workspace_path: Path) -> Path:
    return workspace_dir(workspace_path) / "sessions"


@dataclass
class WorkspaceSettings:
    """单个工作区的运行时配置（持久化在 <workspace>/.scriptordb/settings.json）。"""

    workspace_id: str
    name: str
    path: Path
    db_url: str = ""
    llm_provider: str = "openai"
    llm_model: Optional[str] = None
    default_models: dict[str, str] = field(default_factory=dict)
    auto_restore_sessions: bool = True

    def __post_init__(self) -> None:
        if not self.db_url:
            self.db_url = f"sqlite:///{self.path / 'scriptordb.sqlite'}"

    @classmethod
    def load(cls, workspace_path: Path, workspace_id: str, name: str) -> "WorkspaceSettings":
        cfg_file = workspace_settings_file(workspace_path)
        defaults = cls(workspace_id=workspace_id, name=name, path=workspace_path)
        if not cfg_file.exists():
            return defaults
        try:
            payload = json.loads(cfg_file.read_text())
        except (OSError, json.JSONDecodeError):
            return defaults
        if not isinstance(payload, dict):
            return defaults
        ws = cls(
            workspace_id=workspace_id,
            name=str(payload.get("name") or name),
            path=workspace_path,
            db_url=str(payload.get("db_url") or defaults.db_url),
            llm_provider=str(payload.get("llm_provider") or defaults.llm_provider),
            llm_model=payload.get("llm_model"),
            default_models=dict(payload.get("default_models") or {}),
            auto_restore_sessions=bool(
                payload.get("auto_restore_sessions", defaults.auto_restore_sessions)
            ),
        )
        if not ws.llm_model:
            ws.llm_model = ws.default_models.get(ws.llm_provider)
        return ws

    def save(self) -> None:
        target_dir = workspace_dir(self.path)
        target_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = workspace_settings_file(self.path)
        payload = {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "db_url": self.db_url,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "default_models": self.default_models,
            "auto_restore_sessions": self.auto_restore_sessions,
        }
        try:
            cfg_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        except OSError:
            pass


class WorkspaceRegistry:
    """全局工作区注册表（~/.config/scriptordb/workspaces.json）。"""

    def __init__(self, registry_file: Path | None = None) -> None:
        self._registry_file = registry_file or REGISTRY_FILE
        self._data = self._load()

    def _load(self) -> WorkspaceRegistryData:
        if not self._registry_file.exists():
            return WorkspaceRegistryData()
        try:
            payload = json.loads(self._registry_file.read_text())
        except (OSError, json.JSONDecodeError):
            return WorkspaceRegistryData()
        if not isinstance(payload, dict):
            return WorkspaceRegistryData()
        raw_workspaces = payload.get("workspaces", {})
        workspaces: dict[str, WorkspaceRecord] = {}
        if isinstance(raw_workspaces, dict):
            for wid, raw in raw_workspaces.items():
                if not isinstance(raw, dict):
                    continue
                try:
                    workspaces[str(wid)] = WorkspaceRecord(
                        id=str(raw.get("id") or wid),
                        name=str(raw.get("name") or wid),
                        path=str(raw.get("path") or ""),
                        created_at=str(raw.get("created_at") or ""),
                    )
                except Exception:
                    continue
        return WorkspaceRegistryData(
            version=int(payload.get("version", REGISTRY_VERSION)),
            last_active_workspace_id=payload.get("last_active_workspace_id"),
            workspaces=workspaces,
        )

    def _save(self) -> None:
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._data.version,
            "last_active_workspace_id": self._data.last_active_workspace_id,
            "workspaces": {
                wid: asdict(rec) for wid, rec in self._data.workspaces.items()
            },
        }
        try:
            self._registry_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        except OSError:
            pass

    def list(self) -> list[WorkspaceRecord]:
        return list(self._data.workspaces.values())

    def get(self, workspace_id: str) -> WorkspaceRecord:
        rec = self._data.workspaces.get(workspace_id)
        if rec is None:
            raise WorkspaceNotFoundError(f"Workspace '{workspace_id}' not found")
        return rec

    def last_active_id(self) -> str | None:
        return self._data.last_active_workspace_id

    def exists_for_path(self, path: Path) -> WorkspaceRecord | None:
        target = str(Path(path).expanduser().resolve(strict=False))
        for rec in self._data.workspaces.values():
            try:
                if str(Path(rec.path).expanduser().resolve(strict=False)) == target:
                    return rec
            except Exception:
                if rec.path == str(path):
                    return rec
        return None

    def create(self, path: Path, name: str | None = None, db_url: str | None = None) -> WorkspaceRecord:
        resolved = Path(path).expanduser().resolve(strict=False)
        if not resolved.exists():
            raise WorkspaceNotFoundError(f"Workspace path does not exist: {resolved}")
        existing = self.exists_for_path(resolved)
        if existing is not None:
            raise WorkspaceAlreadyExistsError(
                f"Workspace already registered for path: {resolved} (id={existing.id})"
            )
        ws_id = _new_workspace_id()
        rec = WorkspaceRecord(
            id=ws_id,
            name=name or resolved.name or "workspace",
            path=str(resolved),
            created_at=datetime.utcnow().isoformat(),
        )
        self._data.workspaces[ws_id] = rec
        self._save()

        ws_dir = workspace_dir(resolved)
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "sessions").mkdir(parents=True, exist_ok=True)
        ws_settings = WorkspaceSettings.load(resolved, ws_id, rec.name)
        if db_url:
            ws_settings.db_url = db_url
        ws_settings.save()
        return rec

    def remove(self, workspace_id: str, delete_files: bool = False) -> None:
        rec = self.get(workspace_id)
        if delete_files:
            try:
                ws_dir = workspace_dir(Path(rec.path))
                if ws_dir.exists():
                    shutil.rmtree(ws_dir)
            except OSError:
                pass
        self._data.workspaces.pop(workspace_id, None)
        if self._data.last_active_workspace_id == workspace_id:
            self._data.last_active_workspace_id = None
        self._save()

    def rename(self, workspace_id: str, new_name: str) -> WorkspaceRecord:
        rec = self.get(workspace_id)
        rec.name = new_name
        self._save()
        try:
            ws_path = Path(rec.path)
            ws_settings = WorkspaceSettings.load(ws_path, rec.id, new_name)
            ws_settings.name = new_name
            ws_settings.save()
        except Exception:
            pass
        return rec

    def set_last_active(self, workspace_id: str) -> WorkspaceRecord:
        rec = self.get(workspace_id)
        self._data.last_active_workspace_id = rec.id
        self._save()
        return rec

    def clear_last_active(self) -> None:
        self._data.last_active_workspace_id = None
        self._save()


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
