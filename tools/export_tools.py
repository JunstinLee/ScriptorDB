from __future__ import annotations

import os

from pydantic_ai import RunContext

from config.settings import Settings
from tools.errors import _to_tool_error
from tools.tool_result import ToolErrorInfo, ToolResult


def export_excel(
    ctx: RunContext[Settings],
    filepath: str,
    sheets: dict[str, dict],
) -> ToolResult:
    try:
        from openpyxl import Workbook
    except ImportError:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="parameter_error",
                message="openpyxl is not installed. Run: uv sync",
            ),
        )

    try:
        wb = Workbook()
        ws = wb.active
        for sheet_name, sheet_data in sheets.items():
            if ws is not None and ws.title == "Sheet":
                ws.title = sheet_name
            else:
                ws = wb.create_sheet(title=sheet_name)

            columns = sheet_data.get("columns", [])
            data = sheet_data.get("data", [])
            if columns:
                ws.append(columns)
            for row in data:
                ws.append(row)

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        wb.save(filepath)

        total_rows = sum(len(s.get("data", [])) for s in sheets.values())
        abs_path = os.path.abspath(filepath)
        return ToolResult(
            success=True,
            output=f"Exported {len(sheets)} sheet{'s' if len(sheets) != 1 else ''}, {total_rows} row{'s' if total_rows != 1 else ''} to {os.path.basename(filepath)}",
            data={"file": abs_path, "sheets": len(sheets), "total_rows": total_rows},
        )
    except Exception as e:
        return _to_tool_error(e)
