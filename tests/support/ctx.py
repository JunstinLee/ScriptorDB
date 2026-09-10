"""共享测试脚手架：假 RunContext、xlsx 造数、审批自动通过、异步轮询。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic_ai import (
    DeferredToolRequests,
    DeferredToolResults,
    RunContext,
    ToolApproved,
)
from pydantic_ai.models.test import TestModel as PydanticTestModel
from pydantic_ai.usage import RunUsage

from config.settings import Settings


def make_ctx() -> RunContext[Settings]:
    return RunContext(
        deps=Settings(db_url="sqlite:///:memory:"),
        model=PydanticTestModel(),
        usage=RunUsage(),
    )


def write_xlsx(filepath: Path, sheet_name: str, rows: list[list]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active or wb.create_sheet()
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    wb.save(filepath)


def auto_approve_handler(
    ctx: RunContext[Settings],
    requests: DeferredToolRequests,
) -> DeferredToolResults:
    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


async def await_true(flag: Any, timeout: float = 5.0) -> None:
    """轮询等待 flag() 为真，超时抛 TimeoutError。"""

    async def wait():
        while not flag():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


async def wait_for(predicate: Any, timeout: float = 2.0) -> None:
    """await_true 的别名（各测试包历史命名）。"""
    await await_true(predicate, timeout=timeout)


async def collect_until(gen: Any, target_type: str, timeout: float = 5.0):
    """消费事件流直到出现 target_type；返回 (已见事件, 是否命中)。"""
    seen: list[dict] = []
    done = False

    async def consume():
        nonlocal done
        async for ev in gen:
            seen.append(ev)
            if ev.get("type") == target_type:
                done = True
                return

    await asyncio.wait_for(asyncio.create_task(consume()), timeout=timeout)
    return seen, done


async def collect_all(gen: Any, timeout: float = 5.0) -> list[dict]:
    """消费整个事件流并返回全部事件。"""
    seen: list[dict] = []

    async def consume():
        async for ev in gen:
            seen.append(ev)

    await asyncio.wait_for(asyncio.create_task(consume()), timeout=timeout)
    return seen


async def noop_cb(event: Any) -> None:
    return None


async def noop(*args: Any, **kwargs: Any) -> None:
    return None
