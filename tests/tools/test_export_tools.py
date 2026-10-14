from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.ctx import make_ctx, write_xlsx
from tools.data_tools import read_file
from tools.export_tools import export_excel


class TestExportExcel:
    def test_export_excel_basic(self, tmp_path: Path):
        ctx = make_ctx()
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
    async def test_read_excel_preview(self, tmp_path: Path):
        ctx = make_ctx()
        filepath = tmp_path / "test.xlsx"
        write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = await read_file(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data["columns"] == ["name", "age"]
        assert result.data["rows"] == 3
        assert len(result.data["preview"]) == 3
        assert "data" not in result.data

    async def test_read_excel_return_full(self, tmp_path: Path):
        ctx = make_ctx()
        filepath = tmp_path / "test.xlsx"
        write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = await read_file(ctx, str(filepath), return_full=True)
        assert result.success
        assert result.data is not None
        assert result.data["data"] == [["Alice", "30"], ["Bob", "25"], ["Carol", "27"]]
        assert result.data["truncated"] is False

    async def test_read_excel_max_rows(self, tmp_path: Path):
        ctx = make_ctx()
        filepath = tmp_path / "test.xlsx"
        write_xlsx(
            filepath,
            "Data",
            [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 27]],
        )

        result = await read_file(ctx, str(filepath), return_full=True, max_rows=2)
        assert result.success
        assert result.data is not None
        assert len(result.data["data"]) == 2
        assert result.data["truncated"] is True

    async def test_read_excel_not_found(self):
        ctx = make_ctx()
        result = await read_file(ctx, "/nonexistent/file.xlsx")
        assert not result.success
        assert result.error is not None
        assert result.error.category == "resource_not_found"

    async def test_read_excel_invalid_sheet(self, tmp_path: Path):
        ctx = make_ctx()
        filepath = tmp_path / "test.xlsx"
        write_xlsx(filepath, "Data", [["a"], [1]])

        result = await read_file(ctx, str(filepath), sheet_name="Missing")
        assert not result.success
        assert result.error is not None
