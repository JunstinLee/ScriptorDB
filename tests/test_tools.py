from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from tools.errors import ErrorCategory, _to_tool_error, current_error_id
from tools.tool_result import ToolErrorInfo, ToolResult


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
            ErrorCategory.external_service_error,
            ErrorCategory.internal_error,
        }
        assert categories == expected


class TestToToolError:
    def test_sqlite_error(self):
        result = None
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("INVALID SQL")
        except Exception as e:
            result = _to_tool_error(e)
        assert result is not None
        assert result.error is not None
        assert result.error.category == ErrorCategory.parameter_error
        assert "SQL 错误" in result.error.message

    def test_file_not_found(self):
        result = _to_tool_error(FileNotFoundError("missing.txt"))
        assert not result.success
        assert result.error is not None
        assert result.error.category == ErrorCategory.resource_not_found
        assert "missing.txt" in result.error.message

    def test_permission_error(self):
        result = _to_tool_error(PermissionError("access denied"))
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

    def test_generic_error_generates_error_id(self):
        result = _to_tool_error(ValueError("something"))
        assert not result.success
        assert result.error is not None
        assert result.error.category == ErrorCategory.internal_error
        assert "内部错误" in result.error.message

    def test_internal_error_hides_exception_details(self):
        result = _to_tool_error(RuntimeError("db connection failed: host=10.0.0.1"))
        assert not result.success
        assert "10.0.0.1" not in result.error.message
        assert "db connection failed" not in result.error.message
        assert "请联系管理员" in result.error.message

    def test_internal_error_logs_original_exception(self):
        with patch("tools.errors._get_error_logger") as mock_logger:
            mock_log = mock_logger.return_value
            _to_tool_error(ValueError("secret_detail"), error_id="log123")
            mock_log.error.assert_called_once()
            call_args = mock_log.error.call_args
            assert "log123" in call_args[0][1]
            assert "secret_detail" in str(call_args)

    def test_user_visible_error_preserves_message(self):
        result = _to_tool_error(
            sqlite3.OperationalError("no such column: secret_data")
        )
        assert result.error.category == ErrorCategory.parameter_error
        assert "secret_data" in result.error.message

    def test_contextvar_error_id(self):
        token = current_error_id.set("ctx456")
        try:
            result = _to_tool_error(ValueError("oops"))
            assert "ctx456" in result.error.message
        finally:
            current_error_id.reset(token)

    def test_timeout_error_user_visible(self):
        result = _to_tool_error(subprocess.TimeoutExpired(cmd="python", timeout=30))
        assert result.error.category == ErrorCategory.execution_timeout
        assert "超时" in result.error.message
