from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.workspace_paths import workspace_dir, workspace_settings_file


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
    # TODO: 当 UI 支持"单个工作区覆盖全局默认"时，此字段由前端控制
    # 当前版本始终为 True，所有工作区使用全局默认设置
    use_global_defaults: bool = True

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
            use_global_defaults=bool(
                payload.get("use_global_defaults", defaults.use_global_defaults)
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
            "use_global_defaults": self.use_global_defaults,
        }
        try:
            cfg_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        except OSError:
            pass
