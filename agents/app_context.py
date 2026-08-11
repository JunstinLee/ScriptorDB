from __future__ import annotations

from dataclasses import dataclass

from agents.db_agent import resolve_agent
from config.app_config import AppConfig


@dataclass
class AppContext:
    """Server-side agent context: app config plus a cached agent.

    The cached agent is rebuilt whenever the effective signature
    (provider, model, workspace, configured model) changes — e.g. after a
    workspace switch or a model-setting update. Shared across chat sessions
    via `server.dependencies.get_app_context()`.
    """

    config: AppConfig
    _agent: object = None
    _agent_signature: tuple[str, str, str | None, str | None] | None = None

    def resolve_agent(
        self, model: str | None = None, provider: str | None = None
    ) -> object:
        active_provider = provider or self.config.llm_provider
        signature = (
            active_provider,
            model,
            self.config.workspace_id,
            self.config.llm_model,
        )
        if self._agent is not None and self._agent_signature == signature:
            return self._agent
        self._agent = resolve_agent(self.config, model, provider)
        self._agent_signature = signature
        return self._agent
