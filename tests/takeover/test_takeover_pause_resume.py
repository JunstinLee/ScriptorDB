"""人工接管 = run 内部暂停点（而非 run 结束 + 重启）的专项测试。

核心契约：
- 检测到接管后 agent run 挂起在 resume_event 上，不结束、不取消。
- /takeover/complete 通过 resume_event.set() 唤醒同一个 run（无第二次
  agent.run()），恢复后原执行栈继续到 run_end。
- 取消/超时收敛见 test_takeover_cancel_timeout.py；SSE 订阅见 test_takeover_sse.py。
- 恢复时把"用户完成了人工操作"经 RunContext.enqueue 注入对话。
"""

from __future__ import annotations

import asyncio

import pytest

from browser import get_manager
from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.store import get_takeover_checkpoint_store
from runtime.runner.takeover_hook import RunPauseState
from tests.support.ctx import (
    await_true as _await_true,
    collect_until as _collect_until,
    noop_cb as _noop_cb,
)
from tests.support.stubs import patch_store as _patch_store
from tests.support.takeover import (
    FakeAgent,
    finish_run as _finish_run,
    start_and_wait_paused as _start_and_wait_paused,
)


@pytest.fixture(autouse=True)
def _reset_takeover():
    mgr = get_manager()
    mgr.takeover.reset()
    yield
    mgr.takeover.reset()


# ---------- 挂起 / 恢复 ----------


async def test_takeover_pause_holds_run_not_cancelled():
    """接管是 run 内部暂停点：agent task 挂起而非取消，等待 resume 事件。"""
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="block")
    pause = RunPauseState()
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent, pause=pause)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused
    assert any(ev["type"] == "tool_result" for ev in seen)

    # 挂起期间：agent task 存活（未被取消）；探测事件会取消生成器，
    # 因此用时间流逝 + 恢复来验证。
    await asyncio.sleep(0.3)
    assert not agent.cancelled

    # 恢复：唤醒同一 run，agent 仍不被取消
    pause.resume_event.set()
    await asyncio.sleep(0.2)
    assert not agent.cancelled

    await gen.aclose()
    assert agent.cancelled  # 显式关闭才取消内部 task


async def test_takeover_resume_wakes_same_run():
    """resume_event.set() 唤醒同一 run：原执行栈继续到 run_end。"""
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="block")
    pause = RunPauseState()
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent, pause=pause)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused

    # 用户完成接管：记录结果并 resume 唤醒 hook
    mgr.takeover.complete("完成登录")
    agent.release = True
    pause.resume_event.set()

    events = list(seen)
    async for ev in gen:
        events.append(ev)

    assert any(ev["type"] == "run_end" for ev in events)
    assert not agent.cancelled
    assert "".join(str(c) for c in agent.ctx.enqueued) == (
        "系统站点凭证已自动填充至登录表单，请勿读取或重填密码字段，"
        "直接继续后续流程。用户完成了人工操作: 完成登录"
    )


# ---------- orchestrator 层 ----------


async def test_resume_takeover_validates_run_id(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)

    assert orchestrator.run_id

    wrong = orchestrator.resume_takeover("wrong-run-id", "done")
    assert wrong == {"ok": False, "error": "run_mismatch"}

    right = orchestrator.resume_takeover(orchestrator.run_id, "done")
    assert right["ok"] is True
    assert right["status"] == "resumed"
    assert right["run_id"] == orchestrator.run_id

    # 唤醒后原 run 继续执行到完成
    summary = await _finish_run(run_task, agent)
    assert summary["status"] == "completed"
    assert agent.ctx.enqueued
    assert agent.last_prompt == "hi"  # 同一 run，没有第二次 agent.run()


async def test_resume_injects_takeover_result_message(monkeypatch, store):
    """恢复不是重启：同一 run 内把用户操作结果经 enqueue 注入对话。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)
    assert get_takeover_checkpoint_store().get(sid) is not None

    ok = orchestrator.resume_takeover(orchestrator.run_id, "完成登录")
    assert ok["ok"] is True
    summary = await _finish_run(run_task, agent)
    assert summary["status"] == "completed"
    # 正常完成路径必须清理 checkpoint（run_end 终态收敛）
    assert get_takeover_checkpoint_store().get(sid) is None

async def test_checkpoint_uses_orchestrator_session_id(monkeypatch, store):
    """translator 的 session_id 来自 orchestrator 注入，不再读共享 config。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()  # 刻意不设置 chat_session_id
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = asyncio.create_task(orchestrator.start_run("hi", [], _noop_cb))
    await _await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)

    ckpt = get_takeover_checkpoint_store().get(sid)
    assert ckpt is not None
    assert ckpt.session_id == sid
    assert ckpt.run_id == orchestrator.run_id

    # 清理：取消接管结束 run
    orchestrator.cancel_takeover(orchestrator.run_id)
    await _finish_run(run_task, agent)


