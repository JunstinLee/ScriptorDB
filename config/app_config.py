from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.workspace import WorkspaceNotSelectedError


@dataclass
class AppConfig:
    """当前激活工作区的运行时视图（纯数据）。

    初始为空壳（无工作区），需要调用 `load_for_workspace(...)` 或
    `load_default(...)` 之后才能访问 db_url / llm_api_key 等字段。
    """

    llm_provider: str = ""
    db_url: str = ""
    llm_model: str | None = None
    default_models: dict[str, str] = field(default_factory=dict)
    auto_restore_sessions: bool = True

    chat_session_id: str | None = None
    chat_prompt: str | None = None
    run_id: str = ""

    workspace_id: str | None = field(default=None, init=False)
    workspace_name: str | None = field(default=None, init=False)
    workspace_path: Path | None = field(default=None, init=False)

    def require_workspace(self) -> None:
        if not self.workspace_id:
            raise WorkspaceNotSelectedError(
                "No active workspace. Run 'python main.py workspace list' first."
            )

    @property
    def resolved_model(self) -> str:
        from config.models import resolve_model

        return resolve_model(self.llm_provider, self.llm_model)

    def get_default_model(self, provider: str) -> str | None:
        return self.default_models.get(provider)

    def clear(self) -> None:
        self.workspace_id = None
        self.workspace_name = None
        self.workspace_path = None
        self.db_url = ""
        self.llm_provider = ""
        self.llm_model = None
        self.default_models = {}
        self.auto_restore_sessions = True
