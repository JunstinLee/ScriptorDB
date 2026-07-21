from __future__ import annotations

import uuid
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import ValidatedToolArgs
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from config.settings import Settings
from tools.errors import current_error_id


_call_audit_map: dict[str, tuple[str, Any]] = {}


def build_audit_hooks() -> Hooks[Settings]:
    hooks = Hooks[Settings]()

    @hooks.on.before_tool_execute
    async def audit_before(
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
    ) -> ValidatedToolArgs:
        error_id = uuid.uuid4().hex[:12]
        token = current_error_id.set(error_id)
        _call_audit_map[call.tool_call_id] = (error_id, token)
        return args

    @hooks.on.after_tool_execute
    async def audit_after(
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        result: Any,
    ) -> Any:
        error_id, token = _call_audit_map.pop(call.tool_call_id, ("?", None))
        if token is not None:
            current_error_id.reset(token)
        return result

    return hooks


def build_undo_hooks() -> Hooks[Settings]:
    hooks = Hooks[Settings]()

    @hooks.on.before_run
    async def undo_before_run(ctx: RunContext[Settings]) -> None:
        if not ctx.deps.db_url:
            return
        from uuid import uuid4 as _uuid4

        from tools.db_connection import get_engine
        from tools.undo_log import ensure_undo_tables

        engine = get_engine(ctx.deps.db_url, ctx.deps.workspace_id or "")
        ensure_undo_tables(engine)

        session_id = ctx.deps.chat_session_id or _uuid4().hex[:12]
        run_id = ctx.deps.run_id or _uuid4().hex[:12]
        prompt = ctx.deps.chat_prompt or ""
        ctx.deps.chat_session_id = session_id
        ctx.deps.run_id = run_id
        ctx.deps.chat_prompt = prompt
        ctx.deps.current_undo_group_id = None

    @hooks.on.after_run
    async def undo_after_run(ctx: RunContext[Settings], result: Any) -> Any:
        group_id = ctx.deps.current_undo_group_id
        ctx.deps.current_undo_group_id = None
        if group_id is None:
            return result
        from tools.db_connection import get_engine
        from tools.undo_log import finalize_group

        engine = get_engine(ctx.deps.db_url, ctx.deps.workspace_id or "")
        with engine.connect() as conn:
            finalize_group(conn, group_id)
            conn.commit()
        return result

    return hooks
