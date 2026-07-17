from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolErrorInfo(BaseModel):
    category: str = Field(description="ErrorCategory value (parameter_error, permission_error, etc.)")
    message: str = Field(description="Sanitized error message visible to LLM")


class ToolResult(BaseModel):
    success: bool
    output: str | None = Field(default=None, description="Human-readable result summary")
    data: dict[str, Any] | None = Field(default=None, description="Structured data (columns, rows, file paths, etc.)")
    error: ToolErrorInfo | None = Field(default=None, description="Categorized error info, present only when success=False")
