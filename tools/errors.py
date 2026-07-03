from __future__ import annotations

import logging
import subprocess
import traceback
import uuid
from contextvars import ContextVar
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

if TYPE_CHECKING:
    from tools.tool_result import ToolResult, ToolErrorInfo

_error_logger: logging.Logger | None = None


def _get_error_logger() -> logging.Logger:
    global _error_logger
    if _error_logger is None:
        _error_logger = logging.getLogger("scriptordb.errors")
        if not _error_logger.handlers:
            log_dir = Path.home() / ".config" / "scriptordb"
            log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(
                str(log_dir / "scriptordb.log"), encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            _error_logger.addHandler(handler)
            _error_logger.setLevel(logging.DEBUG)
    return _error_logger


current_error_id: ContextVar[str | None] = ContextVar("current_error_id", default=None)


class ErrorCategory(str, Enum):
    parameter_error = "parameter_error"
    permission_error = "permission_error"
    resource_not_found = "resource_not_found"
    execution_timeout = "execution_timeout"
    output_limit_exceeded = "output_limit_exceeded"
    resource_exhausted = "resource_exhausted"
    external_service_error = "external_service_error"
    internal_error = "internal_error"


USER_VISIBLE_CATEGORIES = {
    ErrorCategory.parameter_error,
    ErrorCategory.permission_error,
    ErrorCategory.resource_not_found,
    ErrorCategory.execution_timeout,
    ErrorCategory.output_limit_exceeded,
    ErrorCategory.resource_exhausted,
}


def _sanitize_sql_error(e: Exception) -> str:
    msg = str(e)
    newline = msg.find("\n")
    if newline != -1:
        msg = msg[:newline]
    if len(msg) > 200:
        msg = msg[:197] + "..."
    return msg


def _to_tool_error(e: Exception, error_id: str = "") -> ToolResult:
    from tools.tool_result import ToolErrorInfo, ToolResult

    category = ErrorCategory.internal_error
    message = f"Internal error (ID: {error_id}). Please contact an administrator." if error_id else "Internal error"

    if isinstance(e, OperationalError):
        category = ErrorCategory.parameter_error
        message = f"SQL error: {_sanitize_sql_error(e)}"
    elif isinstance(e, IntegrityError):
        category = ErrorCategory.parameter_error
        message = f"SQL constraint error: {_sanitize_sql_error(e)}"
    elif isinstance(e, ProgrammingError):
        category = ErrorCategory.parameter_error
        message = f"SQL syntax error: {_sanitize_sql_error(e)}"
    elif isinstance(e, FileNotFoundError):
        category = ErrorCategory.resource_not_found
        filename = e.filename if e.filename else str(e).replace("[Errno 2] ", "").replace("No such file or directory: ", "").strip("'\"")
        message = f"File not found: {filename}"
    elif isinstance(e, PermissionError):
        category = ErrorCategory.permission_error
        filename = e.filename if e.filename else str(e).replace("[Errno 13] ", "").replace("Permission denied: ", "").strip("'\"")
        message = f"Permission denied: {filename}"
    elif isinstance(e, subprocess.TimeoutExpired):
        category = ErrorCategory.execution_timeout
        message = f"Execution timed out ({e.timeout}s). Please simplify the code or split into smaller batches."
    elif isinstance(e, TimeoutError):
        category = ErrorCategory.execution_timeout
        message = "Execution timed out. Please simplify the code or split into smaller batches."

    if not error_id:
        error_id = current_error_id.get() or uuid.uuid4().hex[:12]

    if category not in USER_VISIBLE_CATEGORIES:
        logger = _get_error_logger()
        logger.error(
            "[%s] tool_error category=%s exception=%s\n%s",
            error_id,
            category.value,
            repr(e),
            traceback.format_exc(),
        )
        message = f"Internal error (ID: {error_id}). Please contact an administrator."

    return ToolResult(
        success=False,
        error=ToolErrorInfo(category=category, message=message),
    )
