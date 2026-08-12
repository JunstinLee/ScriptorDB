from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from browser import get_manager
from config.settings import Settings


def _auto_approve_handler(
    ctx: RunContext[Settings],
    requests: DeferredToolRequests,
) -> DeferredToolResults:
    from pydantic_ai import ToolApproved

    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


def _make_ctx() -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:"),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


def _write_xlsx(filepath: Path, sheet_name: str, rows: list[list]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active or wb.create_sheet()
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    wb.save(filepath)


@pytest.fixture
def cleanup_browser():
    """Reset the browser manager around each test in browser test files."""
    get_manager().reset()
    yield
    get_manager().reset()


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")
