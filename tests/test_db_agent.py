from __future__ import annotations

import pytest
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.models.test import TestModel as PydanticTestModel

from config.settings import Settings
from tools.db_tools import get_schema, query_database, run_python_code
from tools.data_tools import list_files, read_csv, read_file, write_csv, write_file
from tools.export_tools import export_excel
from tools.viz_tools import plot_chart


def _auto_approve_handler(
    ctx: RunContext[Settings],
    requests: DeferredToolRequests,
) -> DeferredToolResults:
    from pydantic_ai import ToolApproved
    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


@pytest.fixture
def test_agent():
    return Agent(
        model=PydanticTestModel(),
        deps_type=Settings,
        tools=[
            query_database, get_schema,
            read_csv, write_csv,
            read_file, write_file,
            list_files, export_excel, plot_chart,
            run_python_code,
        ],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )



@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")


def test_agent_structure(test_agent):
    assert test_agent.model is not None
    tools_dict = test_agent._function_toolset.tools
    assert len(tools_dict) == 10
    expected = {
        "query_database", "get_schema", "read_csv", "read_file", "list_files",
        "write_csv", "write_file", "export_excel", "run_python_code", "plot_chart",
    }
    actual = set(tools_dict.keys())
    assert actual == expected
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
    assert any(name in tool_names for name in ("run_python_code", "get_schema", "query_database"))
