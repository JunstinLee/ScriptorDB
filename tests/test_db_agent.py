from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel as PydanticTestModel

from config.settings import Settings
from tools.db_tools import get_schema, query_db, run_python_code


@pytest.fixture
def test_agent():
    return Agent(
        model=PydanticTestModel(),
        deps_type=Settings,
        tools=[run_python_code, get_schema, query_db],
    )


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")


def test_agent_structure(test_agent):
    assert test_agent.model is not None
    assert len(test_agent._function_toolset.tools) == 3
    assert test_agent.deps_type is Settings


@pytest.mark.asyncio
async def test_agent_basic_response(test_agent, test_settings):
    m = PydanticTestModel(custom_output_text="Database is ready.")
    with test_agent.override(model=m):
        result = await test_agent.run("List all tables.", deps=test_settings)
        assert result.output == "Database is ready."
    assert m.last_model_request_parameters is not None


@pytest.mark.asyncio
async def test_agent_calls_tools(test_agent, test_settings):
    m = PydanticTestModel()
    with test_agent.override(model=m):
        await test_agent.run("Create a table users with name column.", deps=test_settings)

    params = m.last_model_request_parameters
    assert params is not None
    tool_names = [p.name for p in params.function_tools]
    assert any(name in tool_names for name in ("run_python_code", "get_schema", "query_db"))
