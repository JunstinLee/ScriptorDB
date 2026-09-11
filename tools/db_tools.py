from __future__ import annotations

from pydantic_ai import RunContext

from config.settings import Settings
from tools.tool_decorators import db_tool
from tools.tool_result import ToolResult
from tools.validators import validate_python_code

# 只读 / 写 / undo 工具已按风险域拆分至 db_tools_read / db_tools_write /
# db_tools_undo，本模块保留重导出以兼容既有 `from tools.db_tools import …`
# 调用方（tests/test_db_agent.py、tests/test_streaming.py 等），并承载
# python_sandbox_execute（沙箱执行，独立于 DB 读写的第三个职责）。
# 注意：validators 必须先于子模块 import——db_tools_read/write 顶层都依赖
# validators，若先加载子模块会触发 validators 半初始化循环。
from tools.db_tools_read import get_schema, query_database  # noqa: F401
from tools.db_tools_write import create_table, execute_ddl, write_data  # noqa: F401
from tools.db_tools_undo import (  # noqa: F401
    _build_delete_undo,
    _build_insert_undo,
    _build_update_undo,
)


@db_tool(name="python_sandbox_execute", category="write", timeout=35, max_retries=2, requires_approval=True, validator=validate_python_code, sequential=True)
def python_sandbox_execute(ctx: RunContext[Settings], code: str) -> ToolResult:
    """执行用户明确要求或提供的 Python 代码（受控沙箱内）。

    仅当任务本身需要执行 Python 程序时使用：复杂计算、算法实现、代码验证。
    其他工具返回的结构化结果已是最终数据，可直接使用，无需再经本工具处理。
    """
    from tools.sandbox import sandbox_execute

    try:
        result = sandbox_execute(
            code=code,
            db_url=ctx.deps.db_url,
            timeout=30,
            max_output_kb=10,
        )
    except Exception as e:
        from tools.errors import _to_tool_error

        return _to_tool_error(e)

    if result.exit_code == 0:
        output = f"Code executed successfully: {len(result.stdout)} bytes of output"
        data: dict[str, object] = {
            "stdout": result.stdout,
            "execution_time_ms": result.elapsed_ms,
        }
        # stderr 可能包含沙箱拦截信息或用户代码的警告/错误输出，
        # 不能静默丢弃，否则 agent 会把"0 bytes of output"误判为缓冲问题。
        if result.stderr.strip():
            output += f"\nstderr: {result.stderr.strip()[:2000]}"
            data["stderr"] = result.stderr
        return ToolResult(
            success=True,
            output=output,
            data=data,
        )

    from tools.errors import ErrorCategory
    from tools.tool_result import ToolErrorInfo

    category = ErrorCategory.internal_error
    if result.exit_code == -1:
        category = ErrorCategory.execution_timeout
    elif result.memory_killed or "__SANDBOX_MEMORY_LIMIT__" in result.stderr:
        category = ErrorCategory.resource_exhausted
    elif "SyntaxError" in result.stderr or "NameError" in result.stderr:
        category = ErrorCategory.parameter_error

    if category == ErrorCategory.resource_exhausted:
        message = "Code execution exceeded the 4GB memory limit. Please reduce data size or optimize the code."
    else:
        message = result.stderr.strip() or "Code execution failed"

    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category=category,
            message=message,
        ),
    )
