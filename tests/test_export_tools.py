from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from config.settings import Settings
from tools.export_tools import export_excel, read_excel


def _make_ctx() -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:"),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


class TestExportExcel:
    def test_export_excel_basic(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "output.xlsx"
        result = export_excel(
            ctx,
            str(filepath),
            sheets={
                "Sheet1": {
                    "columns": ["name", "age"],
                    "data": [["Alice", 30], ["Bob", 25]],
                }
            },
        )
        assert result.success
        assert result.data is not None
        assert result.data["sheets"] == 1
        assert result.data["total_rows"] == 2
        assert filepath.exists()


class TestReadExcel:
    def _write_xlsx(self, filepath: Path, sheet_name: str, rows: list[list]):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active or wb.create_sheet()
        ws.title = sheet_name
        for row in rows:
            ws.append(row)
        wb.save(filepath)

    def test_read_excel_preview(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "test.xlsx"
        self._write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = read_excel(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data["columns"] == ["name", "age"]
        assert result.data["rows"] == 3
        assert len(result.data["preview"]) == 3
        assert "data" not in result.data

    def test_read_excel_return_full(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "test.xlsx"
        self._write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = read_excel(ctx, str(filepath), return_full=True)
        assert result.success
        assert result.data is not None
        assert result.data["data"] == [["Alice", "30"], ["Bob", "25"], ["Carol", "27"]]
        assert result.data["truncated"] is False

    def test_read_excel_max_rows(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "test.xlsx"
        self._write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = read_excel(ctx, str(filepath), return_full=True, max_rows=2)
        assert result.success
        assert result.data is not None
        assert len(result.data["data"]) == 2
        assert result.data["truncated"] is True

    def test_read_excel_not_found(self):
        ctx = _make_ctx()
        result = read_excel(ctx, "/nonexistent/file.xlsx")
        assert not result.success
        assert result.error is not None
        assert result.error.category == "resource_not_found"

    def test_read_excel_invalid_sheet(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "test.xlsx"
        self._write_xlsx(filepath, "Data", [["a"], [1]])

        result = read_excel(ctx, str(filepath), sheet_name="Missing")
        assert not result.success
        assert result.error is not None
