from __future__ import annotations

from uuid import uuid4
from pydantic_ai import RunContext

from config.settings import Settings
from config.workspace import workspace_outputs_dir
from tools.errors import _to_tool_error
from tools.tool_decorators import db_tool
from tools.tool_result import ToolErrorInfo, ToolResult


_CHINESE_FONT_CANDIDATES = [
    "PingFang SC",
    "Hiragino Sans GB",
    "STHeiti Medium",
    "STHeiti Light",
    "Hiragino Mincho ProN",
]


def _configure_chinese_font(plt) -> str | None:
    try:
        from matplotlib import font_manager

        available = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:
        return None

    chosen = next((name for name in _CHINESE_FONT_CANDIDATES if name in available), None)
    if chosen is not None:
        plt.rcParams["font.sans-serif"] = [chosen, "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    return chosen


@db_tool(name="plot_chart", category="viz", timeout=30)
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

    _configure_chinese_font(plt)

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

        workspace_path = ctx.deps.workspace_path if ctx.deps else None
        if workspace_path is None:
            return ToolResult(
                success=False,
                error=ToolErrorInfo(
                    category="parameter_error",
                    message="No active workspace. Select a workspace before generating charts.",
                ),
            )

        outputs_dir = workspace_outputs_dir(workspace_path)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        file_id = f"chart_{uuid4().hex[:8]}.png"
        output_path = outputs_dir / file_id
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        del output_file

        return ToolResult(
            success=True,
            output=f"Chart generated: {file_id}",
            data={
                "file": file_id,
                "chart_type": chart_type,
                "title": title,
            },
        )
    except Exception as e:
        return _to_tool_error(e)
