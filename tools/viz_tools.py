from __future__ import annotations

import os

from uuid import uuid4
from pydantic_ai import RunContext

from config.settings import Settings
from tools.errors import _to_tool_error
from tools.tool_result import ToolErrorInfo, ToolResult


def plot_chart(
    ctx: RunContext[Settings],
    chart_type: str,
    x_data: list,
    y_data: list,
    x_label: str = "",
    y_label: str = "",
    title: str = "",
    output_file: str = "",
) -> ToolResult:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="parameter_error",
                message="matplotlib is not installed. Run: uv sync",
            ),
        )

    valid_types = {"line", "bar", "scatter", "pie"}
    if chart_type not in valid_types:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="parameter_error",
                message=f"Unknown chart type: {chart_type}. Valid types: {', '.join(sorted(valid_types))}",
            ),
        )

    try:
        fig, ax = plt.subplots()

        if chart_type == "line":
            ax.plot(x_data, y_data)
        elif chart_type == "bar":
            ax.bar(x_data, y_data)
        elif chart_type == "scatter":
            ax.scatter(x_data, y_data)
        elif chart_type == "pie":
            ax.pie(y_data, labels=x_data, autopct="%1.1f%%")

        if chart_type != "pie":
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
        ax.set_title(title)

        path = output_file or f"chart_{uuid4().hex[:8]}.png"
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        abs_path = os.path.abspath(path)
        return ToolResult(
            success=True,
            output=f"图表已生成: {abs_path}",
            data={"file": abs_path, "chart_type": chart_type},
        )
    except Exception as e:
        return _to_tool_error(e)
