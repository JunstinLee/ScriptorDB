from __future__ import annotations

import os

from pydantic_ai import RunContext

from config.settings import Settings
from tools.pdf.service import extract_pdf
from tools.errors import _to_tool_error
from tools.tool_decorators import db_tool
from tools.tool_result import ToolErrorInfo, ToolResult
from tools.validators import validate_file_path


@db_tool(name="read_pdf", timeout=60, validator=validate_file_path)
async def read_pdf(
    ctx: RunContext[Settings],
    filepath: str,
    max_chars: int = 50000,
) -> ToolResult:
    if not os.path.isfile(filepath):
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )

    try:
        result = await extract_pdf(filepath, max_chars=max_chars)
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
        f"Read {os.path.basename(filepath)}: {len(result.text)} characters"
        f"{' (truncated)' if result.truncated else ''}"
    )
    return ToolResult(
        success=True,
        output=output,
        data={
            "file": filepath,
            "text": result.text,
            "metadata": result.metadata,
            "truncated": result.truncated,
            "characters": len(result.text),
        },
    )
