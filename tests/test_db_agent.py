from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.models.test import TestModel as PydanticTestModel

from config.settings import Settings
from tools.db_tools import get_schema, python_sandbox_execute, query_database
from tools.data_tools import list_files, read_csv, read_file, write_csv, write_file
from tools.export_tools import export_excel
from tools.tool_decorators import get_all_tool_defs
from tools.viz_tools import plot_chart

from tests.conftest import _auto_approve_handler


def test_browser_data_tools_return_object_schema():
    import tools.browser_tools.inspect
    import tools.browser_tools.links
    import tools.browser_tools.table

    object_tools = {
        "browser_extract_table",
        "browser_extract_rows",
        "browser_extract_links",
        "browser_inspect_structure",
    }
    for d in get_all_tool_defs():
        if d.name in object_tools:
            assert d.to_tool().function_schema.return_schema["type"] == "object", d.name


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
            python_sandbox_execute,
        ],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )


def test_agent_structure(test_agent):
    assert test_agent.model is not None
    tools_dict = test_agent._function_toolset.tools
    assert len(tools_dict) == 10
    expected = {
        "query_database", "get_schema", "read_csv", "read_file", "list_files",
        "write_csv", "write_file", "export_excel", "python_sandbox_execute", "plot_chart",
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
    assert any(name in tool_names for name in ("python_sandbox_execute", "get_schema", "query_database"))
