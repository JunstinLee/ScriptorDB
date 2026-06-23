from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.workspace_paths import (
    GLOBAL_CONFIG_DIR,
    REGISTRY_FILE,
    REGISTRY_VERSION,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    workspace_dir,
)
from config.workspace_settings import WorkspaceSettings


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
