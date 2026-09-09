from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Callable

from core.logging_setup import get_logger

logger = get_logger("browser.login_watcher")

# 只上报与登录表单相关的突变（新增控件节点 / 可见性·类型属性变化），压低 evaluate 次数。
_MUTATION_OBSERVER_JS = """() => {
  const relevant = (el) => {
    const tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "button" || tag === "form"
      || tag === "iframe" || tag === "select" || tag === "textarea";
  };
  const observer = new MutationObserver((records) => {
    let fire = false;
    for (const rec of records) {
      if (rec.type === "attributes") {
        if (relevant(rec.target)) { fire = true; break; }
        continue;
      }
      for (const n of rec.addedNodes) {
        if (n.nodeType !== Node.ELEMENT_NODE) continue;
        if (relevant(n) || (n.querySelector && n.querySelector(
          "input, button, form, iframe, select, textarea"))) {
          fire = true; break;
        }
      }
      if (fire) break;
    }
    if (fire) window.__scriptordb_domChanged && window.__scriptordb_domChanged();
  });
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "hidden", "type"],
  });
}"""

_DEBOUNCE_SECONDS = 0.4
_POLL_INTERVAL_SECONDS = 1.5
_PASSWORD_FINGERPRINT_JS = "() => !!document.querySelector('input[type=password]')"
_Signature = tuple[str, tuple[tuple[str, str], ...]]

# 活跃 LoginWatcher 注册表：供「凭证保存成功后重置该页填表记忆」使用
# （保存动作与 watcher 分属不同请求/任务，需经注册表触达实例）。
_active_watchers: set["LoginWatcher"] = set()


def clear_autofill_memory() -> None:
    """清空全部活跃 watcher 的「已试过填表」记忆。

    登录表单样子没变时 watcher 不会重试填表；用户保存凭证后必须清掉
    记忆，下一轮轮询才会带着新凭证重新尝试。没有活跃 watcher（无进行中
    会话/浏览器未开）时为空操作，天然安全。
    """
    for w in list(_active_watchers):
        w._autofill_sig = None
        w._autofill_url = None


class LoginWatcher:
    """页面登录表单观察器：初始检测 + DOM 突变驱动的增量检测。

    登录弹窗常由页面 JS 在两次工具调用之间延迟弹出，after_tool_result 的
    单次快照会漏掉。add_init_script 注入的 MutationObserver 在每次导航后
    自动重装；检测到登录表单即回调 on_detected（去重：签名未变不重复报）。
    run 终结时必须调用 shutdown()，避免常驻任务跨 run 发事件。
    """

    def __init__(
        self,
        page: Any,
        on_detected: Callable[[dict[str, Any]], Any],
        on_autofill_candidate: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self._page = page
        self._on_detected = on_detected
        self._on_autofill_candidate = on_autofill_candidate
        self._started = False
        self._running_task: asyncio.Task | None = None
        self._incremental_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._last_sig: _Signature | None = None
        self._last_reported_url: str | None = None
        # 「这一页已试过填表」记忆：表单签名/URL 变了才重试。
        # 凭证保存成功后由 clear_autofill_memory() 清空，触发重试。
        self._autofill_sig: _Signature | None = None
        self._autofill_url: str | None = None

    @property
    def started(self) -> bool:
        return self._started

    async def start(self) -> None:
        """安装观察器并立即执行一轮初始检测。幂等。"""
        if self._started:
            return
        self._started = True
        _active_watchers.add(self)
        try:
            await self._page.add_init_script(_MUTATION_OBSERVER_JS)
            await self._page.expose_function(
                "__scriptordb_domChanged", self._schedule_incremental
            )
        except Exception as e:
            # 页面已关闭/导航中被回收：降级为仅初始检测，after_tool_result 兜底。
            logger.debug("login_watcher: observer install failed: %s", e)
        if self._running_task is None or self._running_task.done():
            self._running_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._started = False
        _active_watchers.discard(self)
        for task in (self._running_task, self._incremental_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        self._running_task = None
        self._incremental_task = None
        try:
            await self._page.remove_expose_function("__scriptordb_domChanged")
        except Exception:
            pass

    def _schedule_incremental(self) -> None:
        """MutationObserver 回调（页面上下文）。防抖窗口内合并为一次检测。"""
        if not self._started or self._running_task is None:
            return
        if self._incremental_task is None or self._incremental_task.done():
            loop = self._running_task.get_loop()
            self._incremental_task = loop.create_task(self._debounced_drain())

    async def _debounced_drain(self) -> None:
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        await self._drain()

    async def _run(self) -> None:
        await self._drain()
        try:
            while self._started:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                if self._started:
                    await self._drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("login_watcher: loop exited: %s", e)

    async def _drain(self) -> None:
        """一轮增量检测：门卫 → 提取 → 签名去重 → 上报。"""
        if not self._started:
            return
        async with self._lock:
            if not self._started:
                return
            try:
                has_password = bool(
                    await self._page.evaluate(_PASSWORD_FINGERPRINT_JS)
                )
                if not has_password:
                    title = ""
                    try:
                        title = (await self._page.title()) or ""
                    except Exception:
                        pass
                    if not any(kw in title.lower() for kw in
                               ("sign in", "log in", "login", "signin")):
                        self._last_sig = None
                        self._last_reported_url = None
                        return
            except Exception as e:
                logger.debug("login_watcher: fingerprint failed: %s", e)
                return

            try:
                from browser.login_form import extract_login_form

                info = await extract_login_form(self._page)
            except Exception as e:
                logger.debug("login_watcher: extraction failed: %s", e)
                return
            if info is None:
                self._last_sig = None
                self._last_reported_url = None
                self._autofill_sig = None
                self._autofill_url = None
                return

            # 填表尝试独立于事件上报去重：「表单没变就不重复报给前端」是对的，
            # 但不能因此挡住填表——凭证可能刚保存（表单样子没变、键串里已有
            # 新凭证）。填表记忆只在表单签名/URL 变化或 clear_autofill_memory()
            # 时重置，见模块级 clear_autofill_memory()。
            if (
                self._on_autofill_candidate is not None
                and (
                    info.signature() != self._autofill_sig
                    or info.url != self._autofill_url
                )
            ):
                self._autofill_sig = info.signature()
                self._autofill_url = info.url
                try:
                    # 填表回调需要结构化表单(供 try_autofill 读字段)，
                    # 传对象而非 to_dict()
                    await self._on_autofill_candidate(info)
                except Exception as e:
                    logger.debug(
                        "login_watcher: on_autofill_candidate failed: %s", e,
                    )

            if (
                info.signature() == self._last_sig
                and info.url == self._last_reported_url
            ):
                return
            self._last_sig = info.signature()
            self._last_reported_url = info.url
            try:
                await self._on_detected(info.to_dict())
            except Exception as e:
                logger.debug("login_watcher: on_detected failed: %s", e)
