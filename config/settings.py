from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.secrets import get_api_key
from config.models import resolve_model
from config.workspace import (
    GLOBAL_CONFIG_DIR,
    LEGACY_CONFIG_FILE,
    WorkspaceNotSelectedError,
    WorkspaceSettings,
    get_last_active_workspace,
    migrate_legacy,
)
from config.workspace import WorkspaceRegistry

_LEGACY_CONFIG_FILE = LEGACY_CONFIG_FILE


def _load_legacy_config() -> dict:
    if not _LEGACY_CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(_LEGACY_CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_legacy_config(config: dict) -> None:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _LEGACY_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    except OSError:
        pass


@dataclass
class Settings:
    """当前激活工作区的运行时视图。

    初始为空壳（无工作区），需要调用 `load_for_workspace(...)` 或
    `load_default(...)` 之后才能访问 db_url / llm_api_key 等字段。
    """

    llm_provider: str = "openai"
    db_url: str = ""
    llm_model: Optional[str] = field(default=None)
    default_models: dict[str, str] = field(default_factory=dict)
    auto_restore_sessions: bool = True

    workspace_id: str | None = field(default=None, init=False)
    workspace_name: str | None = field(default=None, init=False)
    workspace_path: Path | None = field(default=None, init=False)

    def _require_workspace(self) -> None:
        if not self.workspace_id:
            raise WorkspaceNotSelectedError(
                "No active workspace. Run 'python main.py workspace list' first."
            )

    @property
    def llm_api_key(self) -> str:
        self._require_workspace()
        key = get_api_key(self.llm_provider, self.workspace_id)
        if key is None:
            raise RuntimeError(
                f"No API key found for {self.llm_provider}. Run 'python main.py setup' first."
            )
        return key

    @property
    def resolved_model(self) -> str:
        return resolve_model(self.llm_provider, self.llm_model)

    def set_default_model(self, provider: str, model: str) -> None:
        self._require_workspace()
        self.default_models[provider] = model
        if self.llm_provider == provider:
            self.llm_model = model
        self._persist()

    def get_default_model(self, provider: str) -> str | None:
        return self.default_models.get(provider)

    def set_provider(self, provider: str) -> None:
        self._require_workspace()
        self.llm_provider = provider
        if provider in self.default_models:
            self.llm_model = self.default_models[provider]
        self._persist()

    def set_auto_restore_sessions(self, value: bool) -> None:
        self._require_workspace()
        self.auto_restore_sessions = value
        self._persist()

    def _persist(self) -> None:
        if not self.workspace_path or not self.workspace_id:
            return
        ws_settings = WorkspaceSettings(
            workspace_id=self.workspace_id,
            name=self.workspace_name or "",
            path=self.workspace_path,
            db_url=self.db_url,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            default_models=dict(self.default_models),
            auto_restore_sessions=self.auto_restore_sessions,
        )
        ws_settings.save()

    def load_for_workspace(self, workspace_id: str) -> None:
        registry = WorkspaceRegistry()
        rec = registry.get(workspace_id)
        ws_path = Path(rec.path)
        ws_settings = WorkspaceSettings.load(ws_path, rec.id, rec.name)
        self.workspace_id = rec.id
        self.workspace_name = rec.name
        self.workspace_path = ws_path
        self.db_url = ws_settings.db_url
        self.llm_provider = ws_settings.llm_provider
        self.llm_model = ws_settings.llm_model
        self.default_models = dict(ws_settings.default_models)
        self.auto_restore_sessions = ws_settings.auto_restore_sessions

    def clear(self) -> None:
        self.workspace_id = None
        self.workspace_name = None
        self.workspace_path = None
        self.db_url = ""
        self.llm_provider = "openai"
        self.llm_model = None
        self.default_models = {}
        self.auto_restore_sessions = True


def load_default_workspace() -> bool:
    """在启动时加载默认工作区：自动迁移或读取 last_active。

    返回是否成功加载了一个工作区。
    """
    migrate_legacy()
    rec = get_last_active_workspace()
    if rec is None:
        return False
    settings.load_for_workspace(rec.id)
    return True


settings = Settings()
