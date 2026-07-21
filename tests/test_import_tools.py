from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage
from config.settings import Settings
from tools.db_repository import DatabaseRepository
from tools.import_tools import import_csv_to_db, import_excel_to_db


def _make_ctx() -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:"),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


def _query_table(db_url: str, table_name: str):
    repo = DatabaseRepository(db_url, "")
    rows = repo.execute_query(f'SELECT * FROM "{table_name}"', limit=1000)
    if not rows:
        return [], []
    columns = list(rows[0].keys())
    return columns, [[row[c] for c in columns] for row in rows]


class TestImportCsvToDb:
    def test_import_csv_basic(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.csv"
        filepath.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")

        result = import_csv_to_db(ctx, str(filepath), "csv_basic")
        assert result.success
        assert result.data is not None
        assert result.data["rows_imported"] == 2

        columns, rows = _query_table(ctx.deps.db_url, "csv_basic")
        assert columns == ["name", "age"]
        assert rows == [["Alice", "30"], ["Bob", "25"]]

    def test_import_csv_batches(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.csv"
        lines = ["name,age"] + [f"User{i},{i}" for i in range(5)]
        filepath.write_text("\n".join(lines), encoding="utf-8")

        result = import_csv_to_db(ctx, str(filepath), "csv_batches", batch_size=2)
        assert result.success
        assert result.data is not None
        assert result.data["rows_imported"] == 5

        columns, rows = _query_table(ctx.deps.db_url, "csv_batches")
        assert len(rows) == 5

    def test_import_csv_if_exists_replace(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.csv"
        filepath.write_text("name,age\nAlice,30\n", encoding="utf-8")

        result1 = import_csv_to_db(ctx, str(filepath), "csv_replace", if_exists="replace")
        assert result1.success

        filepath.write_text("name,age\nBob,25\n", encoding="utf-8")
        result2 = import_csv_to_db(ctx, str(filepath), "csv_replace", if_exists="replace")
        assert result2.success

        columns, rows = _query_table(ctx.deps.db_url, "csv_replace")
        assert rows == [["Bob", "25"]]

    def test_import_csv_hooks(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.csv"
        filepath.write_text("name,age\nAlice,30\nBob,12\nCarol,25\n", encoding="utf-8")

        def transform(row: dict) -> dict:
            row["name"] = row["name"].upper()
            return row

        def keep(row: dict) -> bool:
            return int(row["age"]) >= 18

        result = import_csv_to_db(
            ctx,
            str(filepath),
            "csv_hooks",
            row_transform=transform,
            row_filter=keep,
        )
        assert result.success
        assert result.data is not None
        assert result.data["rows_imported"] == 2

        columns, rows = _query_table(ctx.deps.db_url, "csv_hooks")
        assert rows == [["ALICE", "30"], ["CAROL", "25"]]

    def test_import_csv_file_not_found(self):
        ctx = _make_ctx()
        result = import_csv_to_db(ctx, "/nonexistent/data.csv", "missing")
        assert not result.success
        assert result.error is not None
        assert result.error.category == "resource_not_found"


class TestImportExcelToDb:
    def _write_xlsx(self, filepath: Path, sheet_name: str, rows: list[list]):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active or wb.create_sheet()
        ws.title = sheet_name
        for row in rows:
            ws.append(row)
        wb.save(filepath)

    def test_import_excel_basic(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.xlsx"
        self._write_xlsx(filepath, "People", [["name", "age"], ["Alice", 30], ["Bob", 25]])

        result = import_excel_to_db(ctx, str(filepath), "excel_basic")
        assert result.success
        assert result.data is not None
        assert result.data["rows_imported"] == 2

        columns, rows = _query_table(ctx.deps.db_url, "excel_basic")
        assert columns == ["name", "age"]
        assert rows == [["Alice", "30"], ["Bob", "25"]]

    def test_import_excel_hooks(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.xlsx"
        self._write_xlsx(
            filepath,
            "People",
            [["name", "age"], ["Alice", 30], ["Bob", 12], ["Carol", 25]],
        )

        def transform(row: dict) -> dict:
            row["name"] = row["name"].upper()
            return row

        def keep(row: dict) -> bool:
            return int(row["age"]) >= 18

        result = import_excel_to_db(
            ctx,
            str(filepath),
            "excel_hooks",
            row_transform=transform,
            row_filter=keep,
        )
        assert result.success
        assert result.data is not None
        assert result.data["rows_imported"] == 2

        columns, rows = _query_table(ctx.deps.db_url, "excel_hooks")
        assert rows == [["ALICE", "30"], ["CAROL", "25"]]

    def test_import_excel_invalid_sheet(self, tmp_path: Path):
        ctx = _make_ctx()
        filepath = tmp_path / "data.xlsx"
        self._write_xlsx(filepath, "People", [["a"], [1]])

        result = import_excel_to_db(ctx, str(filepath), "excel_missing", sheet_name="Missing")
        assert not result.success
        assert result.error is not None
