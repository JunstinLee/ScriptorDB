from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy import create_engine, text

from config.settings import Settings
from tools.data_tools import list_files, read_csv, read_file, write_csv, write_file
from tools.errors import ErrorCategory, _to_tool_error, current_error_id
from tools.tool_result import ToolErrorInfo, ToolResult


def _make_ctx() -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:"),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, output="done", data={"count": 5})
        assert r.success
        assert r.output == "done"
        assert r.data == {"count": 5}
        assert r.error is None

    def test_error_result(self):
        e = ToolErrorInfo(category="parameter_error", message="bad input")
        r = ToolResult(success=False, error=e)
        assert not r.success
        assert r.error is not None
        assert r.error.category == "parameter_error"
        assert r.error.message == "bad input"

    def test_serialization(self):
        r = ToolResult(success=True, output="ok", data={"rows": 3})
        js = r.model_dump_json()
        parsed = json.loads(js)
        assert parsed["success"] is True
        assert parsed["output"] == "ok"
        assert parsed["data"]["rows"] == 3

    def test_error_serialization(self):
        e = ToolErrorInfo(category="execution_timeout", message="timeout")
        r = ToolResult(success=False, error=e)
        js = r.model_dump_json()
        parsed = json.loads(js)
        assert parsed["success"] is False
        assert parsed["error"]["category"] == "execution_timeout"


class TestErrorCategory:
    def test_all_categories(self):
        categories = set(ErrorCategory.__members__.values())
        expected = {
            ErrorCategory.parameter_error,
            ErrorCategory.permission_error,
            ErrorCategory.resource_not_found,
            ErrorCategory.execution_timeout,
            ErrorCategory.output_limit_exceeded,
            ErrorCategory.resource_exhausted,
            ErrorCategory.external_service_error,
            ErrorCategory.internal_error,
        }
        assert categories == expected


class TestToToolError:
    def test_sql_error(self):
        result = None
        try:
            engine = create_engine("sqlite:///:memory:")
            with engine.connect() as conn:
                conn.execute(text("INVALID SQL"))
        except Exception as e:
            result = _to_tool_error(e)
        assert result is not None
        assert result.error is not None
        assert result.error.category == ErrorCategory.parameter_error
        assert "SQL 错误" in result.error.message

    def test_file_not_found(self):
        result = _to_tool_error(FileNotFoundError(2, "No such file", "missing.txt"))
        assert not result.success
        assert result.error is not None
        assert result.error.category == ErrorCategory.resource_not_found
        assert "missing.txt" in result.error.message

    def test_permission_error(self):
        result = _to_tool_error(PermissionError(13, "denied", "secret.txt"))
        assert not result.success
        assert result.error is not None
        assert result.error.category == ErrorCategory.permission_error

    def test_generic_error_with_error_id(self):
        result = _to_tool_error(ValueError("something"), error_id="test123")
        assert not result.success
        assert result.error is not None
        assert result.error.category == ErrorCategory.internal_error
        assert "test123" in result.error.message
        assert "请联系管理员" in result.error.message

    def test_internal_error_hides_exception_details(self):
        result = _to_tool_error(RuntimeError("db connection failed: host=10.0.0.1"))
        assert not result.success
        assert "10.0.0.1" not in result.error.message
        assert "db connection failed" not in result.error.message

    def test_internal_error_logs_original_exception(self):
        with patch("tools.errors._get_error_logger") as mock_logger:
            mock_log = mock_logger.return_value
            _to_tool_error(ValueError("secret_detail"), error_id="log123")
            mock_log.error.assert_called_once()
            call_args = mock_log.error.call_args
            assert "log123" in call_args[0][1]
            assert "secret_detail" in str(call_args)

    def test_user_visible_error_preserves_message(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
            conn.commit()
        result = None
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT secret_data FROM t"))
        except Exception as e:
            result = _to_tool_error(e)
        assert result is not None
        assert result.error is not None
        assert result.error.category == ErrorCategory.parameter_error
        assert "secret_data" in result.error.message

    def test_contextvar_error_id(self):
        token = current_error_id.set("ctx456")
        try:
            result = _to_tool_error(ValueError("oops"))
            assert "ctx456" in result.error.message
        finally:
            current_error_id.reset(token)


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
