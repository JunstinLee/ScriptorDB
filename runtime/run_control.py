from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage, ToolReturnPart

from tools.tool_result import ToolResult

_MIN_HITS = 2

_DATE_EN_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")
_URL_RE = re.compile(r"https?://([^/\s?#]+)")
_FORM_RE = re.compile(r"\bForm\s+[0-9][0-9A-Z-]*\b", re.IGNORECASE)
_INT_RE = re.compile(r"\d+")

_RETRY_MESSAGE = (
    "工具已经返回了结果，但你的回复没有把这些结果呈现给用户。"
    "请直接把工具返回的关键内容（如记录数、日期、表单类型、链接等）包含在回答中，再结束。"
)


def _collect_from_text(text: str, markers: set[str]) -> None:
    if not text:
        return
    markers.update(m.lower() for m in _DATE_EN_RE.findall(text))
    markers.update(_ISO_DATE_RE.findall(text))
    for host in _URL_RE.findall(text):
        markers.add(host.lower().removeprefix("www."))
    markers.update(m.lower() for m in _FORM_RE.findall(text))
    markers.update(m for m in _INT_RE.findall(_strip_thousand_separators(text)) if int(m) >= 2)


def _collect_value(value: Any, markers: set[str]) -> None:
    if isinstance(value, ToolResult):
        _collect_from_text(value.output or "", markers)
        _collect_value(value.data, markers)
        return
    if isinstance(value, dict):
        for v in value.values():
            _collect_value(v, markers)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _collect_value(v, markers)
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value >= 2:
            markers.add(str(value))
        return
    if isinstance(value, str):
        _collect_from_text(value, markers)


def extract_result_markers(messages: list[ModelMessage] | None) -> set[str]:
    """Collect key markers (counts, dates, hosts, form ids) from all tool returns."""
    markers: set[str] = set()
    if not messages:
        return markers
    for message in messages:
        for part in getattr(message, "parts", None) or []:
            if isinstance(part, ToolReturnPart):
                _collect_value(part.content, markers)
    return markers


_THOUSAND_SEP_RE = re.compile(r"(?<=\d),(?=\d)")


def _strip_thousand_separators(text: str) -> str:
    """Remove comma thousand separators so '1,007,833' matches marker '1007833'."""
    return _THOUSAND_SEP_RE.sub("", text)


def _hits(markers: set[str], text_lower: str) -> int:
    hits = 0
    normalized: str | None = None
    for marker in markers:
        if marker.isdigit():
            if normalized is None:
                normalized = _strip_thousand_separators(text_lower)
            if re.search(rf"\b{re.escape(marker)}\b", normalized):
                hits += 1
        elif marker in text_lower:
            hits += 1
    return hits


def should_allow_end(
    output: Any,
    *,
    messages: list[ModelMessage] | None,
    retry: int = 0,
    partial_output: bool = False,
) -> bool:
    """End-of-turn check: tool results must be surfaced to the user in the final text.

    - streaming partials and non-str outputs (deferred approval path) pass through
    - a run that used no tools (plain Q&A) has no markers and always passes
    - the final text must contain at least `_MIN_HITS` markers from tool results
    - when the tool returns only one distinct marker, hitting it is enough
    - one output retry is allowed before we accept whatever the model produces
    """
    if partial_output:
        return True
    if not isinstance(output, str):
        return True
    if retry >= 1:
        return True
    markers = extract_result_markers(messages)
    if not markers:
        return True
    return _hits(markers, output.lower()) >= min(_MIN_HITS, len(markers))


def build_output_validator() -> Callable[[RunContext[Any], Any], Awaitable[Any]]:
    async def validate_output(ctx: RunContext[Any], output: Any) -> Any:
        allowed = should_allow_end(
            output,
            messages=ctx.messages,
            retry=ctx.retry or 0,
            partial_output=bool(ctx.partial_output),
        )
        if allowed:
            return output
        raise ModelRetry(_RETRY_MESSAGE)

    return validate_output
