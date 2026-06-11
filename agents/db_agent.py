from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config.models import resolve_model
from config.secrets import SUPPORTED_PROVIDERS, get_api_key
from config.settings import Settings
from tools.db_tools import get_schema, query_db, run_python_code

_agent: Agent[Settings] | None = None


def get_agent(model: str | None = None, provider: str | None = None) -> Agent[Settings]:
    global _agent
    if _agent is None or model is not None or provider is not None:
        active_provider = provider or Settings().llm_provider
        resolved_model = (
            resolve_model(active_provider, model) if model else Settings().resolved_model
        )

        if active_provider in ("nim", "together"):
            api_key = get_api_key(active_provider)
            config = SUPPORTED_PROVIDERS[active_provider]
            model_name = resolved_model.split(":", 1)[-1]
            _agent = Agent(
                model=OpenAIChatModel(
                    model_name,
                    provider=OpenAIProvider(base_url=config.base_url, api_key=api_key),
                ),
                deps_type=Settings,
                tools=[run_python_code, get_schema, query_db],
            )
        else:
            _agent = Agent(
                model=resolved_model,
                deps_type=Settings,
                tools=[run_python_code, get_schema, query_db],
            )
    return _agent
