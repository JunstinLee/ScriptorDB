from __future__ import annotations

"""Agent run pipeline: event translation, lifecycle, takeover hook, and helpers.

Consumers should keep importing `run_agent_stream` from `server.agent_runner`
(the backwards-compatible facade) unless they need the internals.
"""

from server.runner.events import (
    browser_action_event,
    human_takeover_request_event,
    normalize_tool_content,
    parse_tool_args,
)
from server.runner.lifecycle import run_agent_stream
from server.runner.takeover_hook import AfterToolContext, BrowserTakeoverHook
from server.runner.translator import EventTranslator

__all__ = [
    "AfterToolContext",
    "BrowserTakeoverHook",
    "EventTranslator",
    "browser_action_event",
    "human_takeover_request_event",
    "normalize_tool_content",
    "parse_tool_args",
    "run_agent_stream",
]
