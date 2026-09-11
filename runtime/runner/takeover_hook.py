from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelRequest

from core.logging_setup import get_logger
from runtime.approval.store import PendingTakeover, get_takeover_checkpoint_store
from runtime.run_tracker import utc_now_iso
from browser.takeover import HumanTakeoverState
from runtime.runner.events import (
    browser_action_event,
    human_takeover_request_event,
    login_flow_status_event,
)

logger = get_logger("agent_runner.takeover")

# autofill 完成（configured + fill_ok）后注入模型的提示：让模型知道系统
# 已代填凭证，不要读取/重填密码字段。同一实例只注入一次，避免长 run 中
# 每次浏览器工具结果重复塞同句累积上下文（实例随 run 新建，标志随实例重置）。
_SYSTEM_FILL_HINT = (
    "系统站点凭证已自动填充至登录表单，请勿读取或重填密码字段，直接继续后续流程"
)


class TakeoverCancelledError(Exception):
    """run 内信号：人工接管被取消/超时，终止本次 run。

    hook 调用 ctx.cancel() 后抛出；lifecycle 捕获后转为 takeover_cancelled
    终态事件。即使 pydantic-ai 对 event_stream_handler 的异常做包装，
    ctx.cancel() 触发的 RunCancelled 也会由 lifecycle 兜底捕获。
    """


@dataclass
class RunPauseState:
    """当前 run 的人工接管暂停状态。

    orchestrator 为每个活跃 run 持有一个实例：检测到接管后 hook 挂起在
    resume_event.wait()，恢复端点 set() 唤醒继续原执行栈；取消/超时则置
    cancelled 后唤醒，hook 转而调用 ctx.cancel() 终止本次 run。
    """

    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False

    def cancel_run(self) -> None:
        """取消语义：唤醒挂起的 run，并标记为取消（而非恢复）。"""
        self.cancelled = True
        self.resume_event.set()


@dataclass
class AfterToolContext:
    """Everything the takeover hook needs to inspect/pause after a browser tool result."""

    queue: Any  # asyncio.Queue[dict]
    tool_name: str
    success: bool
    session_id: str
    run_id: str
    checkpoint_id: str
    prompt: str
    message_history: list[ModelMessage]
    tool_parts: list[Any]
    tool_invocations: list[dict[str, Any]]
    final_output: str
    ctx: Any = None  # RunContext：恢复时注入接管结果消息（取消走 TakeoverCancelledError）
    pause: RunPauseState | None = None


async def _pause_and_wait(
    ctx: AfterToolContext,
    mgr: Any,
    login_form: dict[str, Any] | None,
) -> None:
    """唯一挂起块：enter_waiting + 存 checkpoint + 推事件 + resume_event.wait()。

    03 方案：autofill/decide_takeover 不触碰 takeover manager；所有决策分支
    统一在此挂起，不复制挂起代码。
    """
    takeover = mgr.takeover
    takeover.enter_waiting(
        on_timeout=ctx.pause.cancel_run if ctx.pause else None
    )
    logger.warning(
        "agent paused for takeover reason=%s trigger=%s",
        takeover.reason, takeover.trigger,
    )
    checkpoint = PendingTakeover(
        session_id=ctx.session_id,
        run_id=ctx.run_id,
        checkpoint_id=ctx.checkpoint_id,
        prompt=ctx.prompt,
        message_history=list(ctx.message_history),
        turn_new_messages=(
            [ModelRequest(parts=list(ctx.tool_parts))]
            if ctx.tool_parts
            else []
        ),
        tool_invocations=list(ctx.tool_invocations),
        final_output=ctx.final_output,
        reason=takeover.reason,
        trigger=takeover.trigger,
        created_at=utc_now_iso(),
        login_form=login_form,
    )
    get_takeover_checkpoint_store().add(checkpoint)
    state_after = await mgr.get_state()
    await ctx.queue.put(human_takeover_request_event(
        run_id=ctx.run_id,
        checkpoint_id=ctx.checkpoint_id,
        reason=takeover.reason,
        trigger=takeover.trigger,
        current_url=state_after.get("url", ""),
        screenshot_available=state_after.get("screenshot_available", False),
        timestamp=utc_now_iso(),
        login_form=login_form,
    ))
    if ctx.pause is None:
        # 无暂停状态（理论不出现）：仅通知前端，不挂起。
        return
    # 挂起：agent.run() 的执行停在这里，等待恢复或取消。
    await ctx.pause.resume_event.wait()
    if ctx.pause.cancelled:
        logger.warning(
            "takeover cancelled during pause, cancelling run run_id=%s",
            ctx.run_id,
        )
        # 单一取消通道：自定义异常终止 run（不依赖 pydantic-ai 版本差异）
        raise TakeoverCancelledError(ctx.run_id)
    # 恢复：允许下一次挂起，并把用户操作结果注入对话。
    ctx.pause.resume_event.clear()
    result = takeover.result or ""
    logger.info("takeover resumed run_id=%s result=%s", ctx.run_id, result)
    if ctx.ctx is not None and result:
        try:
            await ctx.ctx.enqueue(f"{_SYSTEM_FILL_HINT}。用户完成了人工操作: {result}")
        except Exception as e:
            logger.debug("enqueue takeover result failed: %s", e)


class BrowserTakeoverHook:
    """Cross-cutting browser human-takeover check after browser tool results.

    Injectable: the translator depends on this interface rather than on the
    browser package, so it can be unit-tested with a fake hook.

    决策时序（03 autofill 方案）：
      0) 裸提取登录表单（extract_login_form，不走 manager.detect_login_form——
         后者带签名去重会把「未配置→保存→重登」场景的表单吞掉）。非登录页
         info=None → 跳过 autofill，走原 detect_takeover() 人工检测。
      1) 登录页：autofill 填长凭证 + 推 login_flow_status + 纯函数 decide_takeover
         产出接管决策（decision 不触碰 takeover manager）。
      2) 原 detect_takeover()（保持原样）：处理非登录人工场景；登录页若
         decision 未要求接管，其 login/mfa 误触发在此置 DETECTED。
      3) 唯一挂起块（唯一 enter_waiting 调用点）按 decision.kind 归一：
         kind=reset → reset 掉误触发；kind=pause(+override_reason) →
         经 takeover.retrigger() 覆盖 reason/trigger（otp 引导/填失败）后挂起；
         decision=None / kind=none → 原样挂起（不做任何覆盖）。

    调用点频率控制：extract_login_form 每次 tool 结果都做 DOM evaluate，是非
    登录页大头成本。按「页面内容指纹」做短时跳过——URL/标题/密码框任一变即
    失效；避免用签名去重（否则「未配置→保存→重登」的同 URL 新页会被吞）。
    跨 run 场景安全：run 挂起时本对象不持有该 URL 的待办，恢复后由新 URL/
    标题变化自然重提取。
    """

    def __init__(self) -> None:
        self._last_login_url: str | None = None
        self._last_login_sig: tuple[str, tuple[tuple[str, str], ...]] | None = None
        self._miss_url: str | None = None
        # 非登录页跳过指纹：(url, title, has_password)
        self._miss_fp: tuple[str, str, bool] | None = None
        # key = (run_id, page)：同 run 同页只启动一次；run 终结由 shutdown 停止
        self._watchers: dict[tuple[str, int], Any] = {}
        # autofill 完成提示是否已注入（同实例只注入一次）
        self._hint_injected: bool = False

    async def _ensure_watcher(
        self,
        ctx: AfterToolContext,
        page: Any,
    ) -> None:
        """确保当前 run 当前页面已启动 LoginWatcher（幂等）。"""
        if page is None or ctx.queue is None:
            return
        key = (ctx.run_id, id(page))
        if key in self._watchers:
            return
        try:
            from browser.login_watcher import LoginWatcher

            async def on_detected(login_form: dict[str, Any]) -> None:
                try:
                    from runtime.runner.events import login_form_detected_event

                    await ctx.queue.put(login_form_detected_event(
                        run_id=ctx.run_id,
                        login_form=login_form,
                    ))
                except Exception as e:
                    logger.debug(
                        "takeover_hook: login_form_detected push failed: %s", e,
                    )

            async def on_autofill_candidate(login_form: Any) -> None:
                # watcher 发现登录页(含保存凭证后表单未变的重试) → 试着填表。
                # 只填 + 推状态，不唤醒 agent：agent 若正挂起，等用户点 Finish
                # 恢复(保持既有接管语义)；若没挂起，其下一浏览器工具结果仍会
                # 走 after_tool_result 原路径。try_autofill 只填空槽，重复安全。
                try:
                    from browser.autofill import try_autofill
                    from runtime.runner.events import login_flow_status_event

                    deps = getattr(ctx.ctx, "deps", None) if ctx.ctx is not None else None
                    workspace_id = getattr(deps, "workspace_id", None)
                    result = await try_autofill(page, login_form, workspace_id)
                except Exception as e:
                    logger.debug(
                        "takeover_hook: watcher autofill failed: %s", e,
                    )
                    return
                if result is None:
                    return
                try:
                    await ctx.queue.put(login_flow_status_event(
                        run_id=ctx.run_id,
                        status=result.status,
                    ))
                except Exception as e:
                    logger.debug(
                        "takeover_hook: login_flow_status push failed: %s", e,
                    )

            watcher = LoginWatcher(
                page=page,
                on_detected=on_detected,
                on_autofill_candidate=on_autofill_candidate,
            )
            await watcher.start()
            self._watchers[key] = watcher
            logger.info(
                "takeover_hook: login watcher started run=%s page=%s url=%s",
                ctx.run_id, id(page), page.url,
            )
        except Exception as e:
            # watcher 失败只影响弹窗增量检测；after_tool_result 快照仍兜底
            logger.debug("takeover_hook: login watcher start failed: %s", e)

    async def shutdown(self, run_id: str | None = None) -> None:
        """停止该 run 注册的全部 LoginWatcher（run_id 为空时清理全部）。"""
        keys = [
            k for k in self._watchers
            if run_id is None or k[0] == run_id
        ]
        for key in keys:
            watcher = self._watchers.pop(key, None)
            if watcher is not None:
                try:
                    await watcher.stop()
                except Exception as e:
                    logger.debug(
                        "takeover_hook: login watcher stop failed: %s", e,
                    )

    async def after_tool_result(self, ctx: AfterToolContext) -> None:
        if not ctx.tool_name.startswith("browser_"):
            return
        try:
            from browser import get_manager

            mgr = get_manager()
            state = await mgr.get_state()
            actions = state.get("actions", [])
            if actions:
                latest = actions[-1]
                await ctx.queue.put(browser_action_event(
                    run_id=ctx.run_id,
                    tool=latest.get("tool", ctx.tool_name),
                    selector=latest.get("selector", ""),
                    coords=latest.get("coords", {}),
                    success=latest.get("success", ctx.success),
                    detail=latest.get("detail", ""),
                    timestamp=latest.get("timestamp", utc_now_iso()),
                ))

            decision: Any = None
            login_form: dict[str, Any] | None = None
            page: Any = None
            info = None
            skip_autofill = False  # 命中页面级缓存：跳过提取或跳过 autofill/事件
            try:
                from browser.login_form import extract_login_form

                page = mgr.page() if mgr else None
                if page is not None:
                    # 初始 + DOM 突变驱动的增量检测（覆盖两次工具调用之间弹出的登录弹窗）
                    await self._ensure_watcher(ctx, page)
                    # 页面级指纹：URL + 标题 + 是否有密码框（轻量，非登录页大头成本）。
                    # 指纹未变 → 跳过提取；变了 → 重新探测。
                    title = ""
                    has_password = False
                    try:
                        title = (await page.title()) or ""
                        has_password = bool(
                            await page.evaluate(
                                "() => !!document.querySelector('input[type=password]')"
                            )
                        )
                    except Exception:
                        pass  # 指纹获取失败：退化为每次提取
                    fp = (page.url, title, has_password)

                    if self._miss_url is not None and fp == self._miss_fp:
                        # 非登录页且页面未变：跳过本次提取
                        info = None
                    elif (
                        self._last_login_url == page.url
                        and self._last_login_sig is not None
                    ):
                        # 登录页且 URL 未变：重提取确认字段签名是否变化。
                        # 签名未变 → 保留 info（供 checkpoint），但跳过 autofill/事件；
                        # 签名变了（重登/表单变化）→ 走正常 autofill。
                        info = await extract_login_form(page)
                        if (
                            info is not None
                            and info.signature() == self._last_login_sig
                        ):
                            skip_autofill = True
                        self._last_login_url = None
                        self._last_login_sig = None
                    else:
                        info = await extract_login_form(page)

                    # 记录本次指纹结果
                    if info is not None:
                        self._miss_url = None
                        self._miss_fp = None
                        if not skip_autofill:
                            self._last_login_url = info.url
                            self._last_login_sig = info.signature()
                    else:
                        self._miss_url = page.url
                        self._miss_fp = fp
            except Exception as e:
                logger.debug("login form extraction skipped: %s", e)
                info = None
            if info is not None:
                login_form = info.to_dict()
                logger.info(
                    "takeover_hook: 检测到登录表单 tool=%s url=%s fields=%d submit=%s",
                    ctx.tool_name, info.url, len(info.fields),
                    info.submit.selector if info.submit else None,
                )
                if not skip_autofill:
                    result = None
                    try:
                        from browser.autofill import try_autofill

                        deps = getattr(ctx.ctx, "deps", None) if ctx.ctx is not None else None
                        workspace_id = getattr(deps, "workspace_id", None)
                        # workspace_id 为空（无活动工作区/测试）时按未配置处理：仍推状态
                        result = await try_autofill(page, info, workspace_id)
                    except Exception as e:
                        logger.debug("autofill skipped: %s", e)
                    if result is not None:
                        # 登录页：无论配置与否都推 login_flow_status（非敏感状态）
                        await ctx.queue.put(login_flow_status_event(
                            run_id=ctx.run_id,
                            status=result.status,
                        ))
                        decision = result.decision
                        # 系统凭证已自动填充且无填错：注入一次提示，让模型
                        # 知道不要读取/重填密码字段（同一实例只注入一次）。
                        if (
                            result.status.configured
                            and result.status.fill_ok
                            and not self._hint_injected
                            and ctx.ctx is not None
                        ):
                            self._hint_injected = True
                            try:
                                await ctx.ctx.enqueue(_SYSTEM_FILL_HINT)
                            except Exception as e:
                                logger.debug(
                                    "takeover_hook: autofill hint enqueue failed: %s",
                                    e,
                                )

            try:
                # 1) 原有人工触发检测（保持原样）：非登录人工场景（图形验证码/滑块/
                #    antibot/OAuth/超时/元素失败）由 detect_takeover() 触发；登录页
                #    场景若上面 decision 未要求接管（fill_ok 且无 otp），这里会把
                #    login/mfa 误触发置 DETECTED，交由下方挂起块按 decision reset。
                await mgr.detect_takeover()
            except Exception as e:
                logger.debug("takeover detection skipped: %s", e)

            takeover = mgr.takeover if mgr else None
            # 2) 唯一挂起块（唯一 enter_waiting 调用点）按 decision.kind 归一：
            #    reset → 清误触发；pause(+override) → retrigger 后挂起；
            #    decision=None（非登录页）或 kind=none → 原样挂起。
            if takeover and takeover.should_pause_agent():
                if decision is not None and decision.kind == "reset":
                    # fill_ok 且无 otp：清掉 login 页误触发的接管，agent 继续
                    logger.info(
                        "takeover_hook: autofill 完成无验证码，reset 登录页误触发接管 tool=%s",
                        ctx.tool_name,
                    )
                    takeover.reset()
                elif decision is not None and decision.kind == "pause":
                    if decision.override_reason:
                        # otp 引导 / 填失败：经状态机入口覆盖 reason/trigger
                        takeover.retrigger(
                            decision.reason, decision.trigger,
                            url=page.url if page is not None else "",
                        )
                    # 未配置场景（override=False）保留检测阶段触发值，仅进入挂起
                    await _pause_and_wait(ctx, mgr, login_form)
                else:
                    # decision=None（非登录页 detect_takeover 触发）或
                    # decision.kind == "none"：原样挂起，不做任何覆盖
                    await _pause_and_wait(ctx, mgr, login_form)
        except Exception as e:
            if isinstance(e, TakeoverCancelledError):
                raise
            logger.debug("browser takeover check skipped: %s", e)
