from __future__ import annotations

from pydantic_ai import Agent

from config import secrets
from config.settings import Settings
from tools.db_tools import get_schema, query_db, run_python_code

_agent: Agent[Settings] | None = None


def get_agent(model: str | None = None, provider: str | None = None) -> Agent[Settings]:
    global _agent
    if _agent is None or model is not None or provider is not None:
        resolved_model = model or (
            secrets.SUPPORTED_PROVIDERS[provider] if provider
            else Settings().llm_model
        )
        _agent = Agent(
            model=resolved_model,
            deps_type=Settings,
            tools=[run_python_code, get_schema, query_db],
        )
    return _agent
