"""登录表单探测：页面指纹缓存 + LoginWatcher 生命周期 + 提取。

从 :mod:`runtime.runner.takeover_hook` 抽出。hook 负责编排（autofill / 决策 /
挂起），本类只负责「当前页有没有登录表单」这一件事，含跨工具调用的指纹缓存。
"""

from __future__ import annotations

from typing import Any

from core.logging_setup import get_logger

logger = get_logger("agent_runner.takeover")


class LoginFormProbe:
    """当前页登录表单探测。

    - 页面级指纹（URL + 标题 + 是否有密码框）：未变则跳过提取（非登录页大头成本）。
    - 登录页 URL 未变时重提取确认字段签名；签名未变则标记 ``skip_autofill``
      （保留 info 供 checkpoint，但不重复填表/推事件）。
    - MutationObserver watcher：覆盖两次工具调用之间弹出的登录弹窗。
    """

    def __init__(self) -> None:
        self._last_login_url: str | None = None
        self._last_login_sig: tuple[str, tuple[tuple[str, str], ...]] | None = None
        self._miss_url: str | None = None
        # 非登录页跳过指纹：(url, title, has_password)
        self._miss_fp: tuple[str, str, bool] | None = None
        # key = (run_id, page)：同 run 同页只启动一次；run 终结由 shutdown 停止
        self._watchers: dict[tuple[str, int], Any] = {}

    async def ensure_watcher(self, ctx, page) -> None:
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

    async def extract(self, page) -> tuple[Any | None, bool]:
        """提取当前页登录表单，返回 ``(LoginFormInfo | None, skip_autofill)``。

        页面指纹未变（非登录页）→ 跳过提取；登录页 URL 未变则重提取确认签名，
        签名未变标记 ``skip_autofill``。
        """
        info = None
        skip_autofill = False
        try:
            from browser.login_form import extract_login_form

            if page is not None:
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
        return info, skip_autofill
