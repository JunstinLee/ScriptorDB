from __future__ import annotations

import os

from pydantic_ai import RunContext

from config.settings import Settings
from services.pdf_service import extract_pdf
from tools.errors import _to_tool_error
from tools.tool_decorators import db_tool
from tools.tool_result import ToolErrorInfo, ToolResult
from tools.validators import validate_file_path


@db_tool(name="read_pdf", timeout=60, validator=validate_file_path)
async def read_pdf(
    ctx: RunContext[Settings],
    path: str,
    max_chars: int = 50000,
) -> ToolResult:
    if not os.path.isfile(path):
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {path}",
            ),
        )

    try:
        result = await extract_pdf(path, max_chars=max_chars)
    except Exception as e:
        return _to_tool_error(e)

    if result.error:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="parse_error",
                message=f"Failed to extract PDF text: {result.error}",
            ),
        )

    output = (
        f"Read {os.path.basename(path)}: {len(result.text)} characters"
        f"{' (truncated)' if result.truncated else ''}"
    )
    return ToolResult(
        success=True,
        output=output,
        data={
            "file": path,
            "text": result.text,
            "metadata": result.metadata,
            "truncated": result.truncated,
            "characters": len(result.text),
        },
    )
