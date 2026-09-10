from __future__ import annotations

import json

from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from config.settings import Settings
from tools.data_tools import list_files, read_csv, read_file, write_csv, write_file

from tests.conftest import _make_ctx


class TestReadCsv:
    def test_read_csv_basic(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "test.csv"
        filepath.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")

        result = read_csv(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data["columns"] == ["name", "age"]
        assert result.data["rows"] == 2
        assert len(result.data["preview"]) == 2

    def test_read_csv_not_found(self):
        ctx = _make_ctx()
        result = read_csv(ctx, "/nonexistent/file.csv")
        assert not result.success
        assert result.error is not None
        assert result.error.category == "resource_not_found"

    def test_read_csv_empty(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "empty.csv"
        filepath.write_text("name,age\n", encoding="utf-8")

        result = read_csv(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data["rows"] == 0

    def test_read_csv_return_full(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "full.csv"
        filepath.write_text("a,b\n1,2\n3,4\n5,6\n", encoding="utf-8")

        result = read_csv(ctx, str(filepath), return_full=True)
        assert result.success
        assert result.data is not None
        assert result.data["data"] == [["1", "2"], ["3", "4"], ["5", "6"]]
        assert result.data["truncated"] is False

    def test_read_csv_return_full_max_rows(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "full.csv"
        filepath.write_text("a,b\n1,2\n3,4\n5,6\n", encoding="utf-8")

        result = read_csv(ctx, str(filepath), return_full=True, max_rows=2)
        assert result.success
        assert result.data is not None
        assert len(result.data["data"]) == 2
        assert result.data["truncated"] is True


class TestWriteCsv:
    def test_write_csv_basic(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "output.csv"
        result = write_csv(
            ctx, str(filepath),
            columns=["a", "b"],
            data=[["1", "2"], ["3", "4"]],
        )
        assert result.success
        assert result.data is not None
        assert result.data["rows_written"] == 2

        content = filepath.read_text()
        assert "a,b" in content
        assert "1,2" in content


class TestReadFile:
    def test_read_text_file(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "hello.txt"
        filepath.write_text("Hello World", encoding="utf-8")

        result = read_file(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data["content"] == "Hello World"

    def test_read_json_file(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "config.json"
        data = {"key": "value", "num": 42}
        filepath.write_text(json.dumps(data), encoding="utf-8")

        result = read_file(ctx, str(filepath))
        assert result.success
        assert result.data is not None
        assert result.data.get("parsed") is True
        assert result.data.get("json_keys") == ["key", "num"]

    def test_read_file_not_found(self):
        ctx = _make_ctx()
        result = read_file(ctx, "/nonexistent/file.txt")
        assert not result.success
        assert result.error is not None
        assert result.error.category == "resource_not_found"

    def test_read_file_truncated(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "large.txt"
        filepath.write_text("x" * 2000, encoding="utf-8")

        result = read_file(ctx, str(filepath), max_size_kb=1)
        assert result.success
        assert result.data is not None
        assert result.data["truncated"] is True


class TestWriteFile:
    def test_write_file_basic(self, tmp_path):
        ctx = _make_ctx()
        filepath = tmp_path / "output.txt"
        result = write_file(ctx, str(filepath), content="Hello File")
        assert result.success
        assert filepath.read_text() == "Hello File"


class TestListFiles:
    def test_list_files_basic(self, tmp_path):
        ctx = _make_ctx()
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.csv").touch()

        result = list_files(ctx, str(tmp_path), "*")
        assert result.success
        assert result.data is not None
        assert result.data["count"] >= 2

    def test_list_files_pattern(self, tmp_path):
        ctx = _make_ctx()
        (tmp_path / "a.csv").touch()
        (tmp_path / "b.txt").touch()

        result = list_files(ctx, str(tmp_path), "*.csv")
        assert result.success
        assert result.data is not None
        assert result.data["count"] == 1
