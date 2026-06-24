from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import ValidatedToolArgs
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from config.settings import Settings
from tools.errors import current_error_id


_LOGGER = logging.getLogger("scriptordb.audit")
_LOG_DIR = Path.home() / ".config" / "scriptordb"
_LOG_FILE = _LOG_DIR / "scriptordb.log"
_call_audit_map: dict[str, tuple[str, Any]] = {}


def _ensure_logger() -> logging.Logger:
    if not _LOGGER.handlers:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.DEBUG)
    return _LOGGER


def _serialize_args(args: ValidatedToolArgs) -> str:
    try:
        return json.dumps(args, ensure_ascii=False, default=str)
    except Exception:
        return str(args)


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
        logger = _ensure_logger()
        logger.info(
            "[%s] tool_call_start  tool=%s  args=%s",
            error_id,
            call.tool_name,
            _serialize_args(args),
        )
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
        logger = _ensure_logger()
        logger.info(
            "[%s] tool_call_end    tool=%s  success=%s",
            error_id,
            call.tool_name,
            getattr(result, "success", True),
        )
        return result

    return hooks
