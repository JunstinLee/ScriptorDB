from __future__ import annotations

"""Agent run pipeline: event translation, lifecycle, takeover hook, and helpers.

Consumers should keep importing `run_agent_stream` from `runtime.agent_runner`
(the backwards-compatible facade) unless they need the internals.
"""

from runtime.runner.events import (
    browser_action_event,
    human_takeover_request_event,
    login_form_detected_event,
    normalize_tool_content,
    parse_tool_args,
)
from runtime.runner.lifecycle import run_agent_stream
from runtime.runner.takeover_hook import AfterToolContext, BrowserTakeoverHook
from runtime.runner.translator import EventTranslator

__all__ = [
    "AfterToolContext",
    "BrowserTakeoverHook",
    "EventTranslator",
    "browser_action_event",
    "human_takeover_request_event",
    "login_form_detected_event",
    "normalize_tool_content",
    "parse_tool_args",
    "run_agent_stream",
]
