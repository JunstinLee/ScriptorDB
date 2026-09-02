from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import re
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, Playwright

from browser.login_form import LoginFormInfo
from browser.tabs import TabManager
from browser.takeover import HumanTakeoverManager, HumanTakeoverState, detect_human_needed, detect_timeout_trigger, detect_element_failure_trigger
from browser.trace import ClickTracer
from core.logging_setup import get_logger

logger = get_logger("browser.manager")

SCREENSHOT_TTL = 30
IDLE_CLOSE_TIMEOUT = 60


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._launching = False

        self._history: list[dict[str, str]] = []
        self._actions: list[dict] = []
        self._last_screenshot: str | None = None
        self._last_screenshot_time: float = 0
        self._launched_at: float | None = None
        self._takeover = HumanTakeoverManager()
        self._nav_timeout_count = 0
        self._element_failure_count: dict[str, int] = {}
        self._auth_origin: str | None = None
        self._login_form_signature: tuple | None = None
        self._downloads_dir: Path | None = None
        self._screencast_connection: object | None = None
        self._idle_close_task: asyncio.Task | None = None
        self._idle_close_deadline: float | None = None
        self.tabs = TabManager()
        self.trace = ClickTracer()

    @property
    def takeover(self) -> HumanTakeoverManager:
        return self._takeover

    def set_downloads_dir(self, path: Path | None) -> None:
        """设置浏览器下载文件的保存目录；None 表示不自动保存。"""
        self._downloads_dir = Path(path) if path else None

    def set_screencast_connection(self, conn: object | None) -> None:
        self._screencast_connection = conn

    def is_screencast_connection(self, conn: object) -> bool:
        return self._screencast_connection is conn

    def clear_screencast_connection(self, conn: object) -> None:
        if self._screencast_connection is conn:
            self._screencast_connection = None

    async def notify_screencast_restart(self) -> None:
        if self._screencast_connection and hasattr(self._screencast_connection, "ensure_screencast_active"):
            await self._screencast_connection.ensure_screencast_active()  # type: ignore[union-attr]

    def record_navigate(self, url: str, title: str = "") -> None:
        self._history.append({
            "url": url,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def record_action(self, tool: str, detail: str, success: bool = True,
                      selector: str = "", coords: dict | None = None,
                      screenshot_path: str = "") -> None:
        self._actions.append({
            "tool": tool,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "selector": selector,
            "coords": coords or {},
            "screenshot_path": screenshot_path,
        })
        if len(self._actions) > 200:
            self._actions = self._actions[-200:]

    def record_screenshot(self, path: str) -> None:
        self._last_screenshot = path
        self._last_screenshot_time = time.monotonic()

    def reset_state(self) -> None:
        self._history.clear()
        self._actions.clear()
        self._last_screenshot = None
        self._last_screenshot_time = 0
        self._launched_at = None
        self._login_form_signature = None

    async def get_state(self) -> dict:
        launched = self.is_launched()
        page = self.page()

        url = None
        title = None
        if launched and page is not None:
            try:
                url = page.url
                title = await page.title()
            except Exception:
                self._clear_browser_refs(log_warning=True)
                launched = False

        tabs_overview = []
        if launched:
            for i, tab in enumerate(self.tabs.pages()):
                try:
                    t_title = await tab.title()
                except Exception:
                    t_title = ""
                tabs_overview.append({
                    "index": i,
                    "active": tab is self.tabs.active_page(),
                    "url": tab.url,
                    "title": t_title,
                })

        return {
            "launched": launched,
            "url": url,
            "title": title,
            "tabs": tabs_overview,
            "screenshot_available": (
                self._last_screenshot is not None
                and (time.monotonic() - self._last_screenshot_time) < SCREENSHOT_TTL
            ),
            "screenshot_path": self._last_screenshot,
            "launched_at": self._launched_at,
            "idle_close_active": self.is_idle_close_scheduled(),
            "idle_close_remaining": self.idle_close_remaining(),
            "actions": list(self._actions),
            "history": list(self._history),
        }

    async def launch(
        self,
        headless: bool = True,
        storage_state: dict | Path | None = None,
        proxy: dict | None = None,
    ) -> str:
        if self._launching:
            return "Browser launch already in progress"
        if self._browser is not None and self._context is None and self._page is None:
            return "Browser already launched"
        if self.is_launched():
            return "Browser already launched"

        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs()

        try:
            from playwright.async_api import async_playwright as ap
        except ImportError:
            return "Playwright is not installed. Run: pip install playwright && playwright install chromium"

        self._launching = True
        try:
            self._playwright = await ap().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            browser_event: object = self._browser.on("disconnected", self._on_browser_disconnected)
            if inspect.isawaitable(browser_event):
                await browser_event
            context_options: dict = {
                "viewport": {"width": 1280, "height": 720},
                "accept_downloads": True,
            }
            if storage_state:
                if isinstance(storage_state, Path):
                    context_options["storage_state"] = str(storage_state)
                else:
                    context_options["storage_state"] = storage_state
            self._context = await self._browser.new_context(**context_options)
            self._context.on("page", lambda page: page.on("response", self._on_page_response))
            self._context.on("download", self._on_download)
            self._page = await self._context.new_page()
            self._page.on("response", self._on_page_response)
            page_event: object = self._page.on("close", self._on_page_closed)
            if inspect.isawaitable(page_event):
                await page_event
            self.tabs.attach(self._context, self._page)
        except Exception as e:
            self.reset()
            return f"Browser launch failed: {e}"
        finally:
            self._launching = False

        self.reset_state()
        self._launched_at = datetime.now(timezone.utc).timestamp()

        mode = "headless" if headless else "visible"
        logger.info(f"browser launched headless=False")
        return f"Browser launched successfully in visible mode"

    async def _on_download(self, download) -> None:
        """任意浏览器下载自动保存到 _downloads_dir（未设置则不保存）。"""
        if not self._downloads_dir:
            logger.warning("download event ignored: downloads dir not configured")
            return
        try:
            if failure := await download.failure():
                logger.warning(f"download failed: {failure}")
                return
            self._downloads_dir.mkdir(parents=True, exist_ok=True)
            filename = _sanitize_filename(download.suggested_filename or "download.bin")
            path = _unique_path(self._downloads_dir, filename)
            await download.save_as(path)
            size = path.stat().st_size
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            _append_manifest(self._downloads_dir, {
                "source_url": download.url if hasattr(download, "url") else "",
                "title": "",
                "publish_date": "",
                "filename": path.name,
                "size": size,
                "sha256": sha256,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"download saved: {path} ({size} bytes)")
        except Exception as e:
            logger.warning(f"download save failed: {e}")

    async def close(self) -> str:
        self.cancel_idle_close()
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._clear_browser_refs()
        self.reset_state()
        logger.info("browser closed")
        return "Browser closed"

    def schedule_idle_close(self, timeout: float = IDLE_CLOSE_TIMEOUT) -> None:
        self.cancel_idle_close()
        if not self.is_launched():
            return
        logger.info(f"scheduling idle close in {timeout}s")
        self._idle_close_deadline = time.monotonic() + timeout
        self._idle_close_task = asyncio.create_task(self._idle_close_after(timeout))

    async def _idle_close_after(self, timeout: float) -> None:
        await asyncio.sleep(timeout)
        self._idle_close_deadline = None
        if not self.is_launched():
            return
        logger.info("idle close timer fired; closing browser")
        await self.close()

    def cancel_idle_close(self) -> None:
        self._idle_close_deadline = None
        if self._idle_close_task and not self._idle_close_task.done():
            self._idle_close_task.cancel()
            self._idle_close_task = None

    def is_idle_close_scheduled(self) -> bool:
        return self._idle_close_task is not None and not self._idle_close_task.done()

    def idle_close_remaining(self) -> int:
        if self._idle_close_deadline is None:
            return 0
        return max(0, int(math.ceil(self._idle_close_deadline - time.monotonic())))

    async def show_window(self):
        if not self.is_launched() or not self._context:
            return
        try:
            page = self.tabs.active_page()
            if page is not None:
                await page.bring_to_front()
        except Exception:
            self._clear_browser_refs(log_warning=True)

    async def load_profile(self, name: str, workspace_id: str) -> bool:
        from config.secrets import get_browser_profile
        from browser.profiles import load_profile as _load_profile

        if not self.is_launched():
            storage_state = get_browser_profile(workspace_id, name)
            if not storage_state:
                return False
            await self.launch(storage_state=storage_state)
            return True

        return await _load_profile(self, name, workspace_id)

    def is_launched(self) -> bool:
        if self._launching:
            return False
        if self._browser_is_alive():
            return True
        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs(log_warning=True)
        return False

    def page(self) -> Page | None:
        if self._launching:
            return None
        if self._browser is None and self._context is None and self._playwright is None:
            return self._page
        if self._browser_is_alive():
            return self.tabs.active_page() or self._page
        if any((self._playwright, self._browser, self._context, self._page)):
            self._clear_browser_refs(log_warning=True)
        return None

    def reset(self) -> None:
        self._clear_browser_refs()
        self._nav_timeout_count = 0
        self._element_failure_count.clear()

    def mark_browser_unavailable(self) -> None:
        self._clear_browser_refs(log_warning=True)

    def _browser_is_alive(self) -> bool:
        if self._browser is None or self._context is None or self._page is None:
            return False
        try:
            return self._browser.is_connected() and not self._page.is_closed()
        except Exception:
            return False

    def _clear_browser_refs(self, log_warning: bool = False) -> None:
        had_browser = any((self._playwright, self._browser, self._context, self._page))
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._launched_at = None
        self._screencast_connection = None
        self._auth_origin = None
        self._takeover.reset()
        self.tabs.detach()
        self.trace.reset()
        if had_browser and log_warning:
            logger.warning("browser target unavailable; cleared Playwright state")

    def _on_browser_disconnected(self, browser: Browser | None = None) -> None:
        if browser is None or browser is self._browser:
            logger.warning("browser disconnected")
            self._clear_browser_refs()

    def _on_page_closed(self, page: Page | None = None) -> None:
        if page is None or page is self._page:
            logger.warning("browser page closed")
            self._clear_browser_refs()

    async def detect_takeover(self) -> bool:
        if not self.is_launched() or self._page is None:
            return False
        if self._takeover.state != HumanTakeoverState.RUNNING:
            return False
        if self._auth_origin is not None:
            logger.warning(f"takeover detected trigger=auth origin={self._auth_origin}")
            return self._takeover.request_takeover(
                reason="HTTP auth required (e.g. Basic Auth) — complete it manually",
                trigger="auth",
                url=self._page.url,
            )
        trigger = await detect_human_needed(self._page)
        if trigger:
            logger.warning(f"takeover detected trigger={trigger.trigger} reason={trigger.reason}")
            return self._takeover.request_takeover(
                reason=trigger.reason,
                trigger=trigger.trigger,
                url=self._page.url,
            )
        return False

    async def detect_login_form(self) -> LoginFormInfo | None:
        """登录页字段提取（自动旁路，非 AI 工具）。

        命中登录页且字段结构相对上次变化时返回 LoginFormInfo，
        否则返回 None（去重：同一 URL+字段签名只产出一次）。
        """
        if not self.is_launched() or self._page is None:
            return None
        if self._takeover.state != HumanTakeoverState.RUNNING:
            return None
        from browser.login_form import extract_login_form
        try:
            info = await extract_login_form(self._page)
        except Exception as e:
            logger.debug("login form detection skipped: %s", e)
            return None
        if info is None:
            self._login_form_signature = None
            return None
        signature = info.signature()
        if signature == self._login_form_signature:
            return None
        self._login_form_signature = signature
        return info

    def record_auth_challenge(self, origin: str) -> None:
        """记录一个待满足的 HTTP 认证挑战（Basic/Digest/NTLM）。

        认证弹框是浏览器原生 UI，DOM 检测不可见，只能靠网络层证据：
        401/407 + WWW-Authenticate 头出现时置位。
        """
        if not origin:
            return
        self._auth_origin = origin
        logger.warning(f"auth challenge recorded origin={origin}")

    def clear_auth_challenge(self, origin: str | None = None) -> None:
        """清除待认证标志：接管结束（完成/取消）时调用。

        该标志只负责触发一次接管；人工处理结束后必须清除，
        否则残留标志会在下一次浏览器动作时立即再次触发接管。
        """
        if origin is None or self._auth_origin == origin:
            self._auth_origin = None

    def auth_challenge_pending(self) -> bool:
        return self._auth_origin is not None

    def auth_challenge_origin(self) -> str | None:
        return self._auth_origin

    def _on_page_response(self, response) -> None:
        """网络层认证挑战跟踪：设置/清除 auth 标志位。

        置位：401/407 且带 WWW-Authenticate 头（此时浏览器会弹认证框）。
        清除：同 origin 出现任何非 401/407 响应（请求已通过认证门禁）。

        仅在 agent 运行期间（takeover 状态为 RUNNING）跟踪。人工接管期间
        用户自行处理认证，后端不观察、不记录、不干预。
        """
        if self._takeover.state != HumanTakeoverState.RUNNING:
            return
        try:
            status = int(response.status)
            headers = response.headers or {}
            origin = netloc_of(response.url)
            if not origin:
                return
            if status in (401, 407) and any(
                k.lower() == "www-authenticate" for k in headers
            ):
                self.record_auth_challenge(origin)
            elif self._auth_origin == origin and status not in (401, 407):
                self._auth_origin = None
        except Exception:
            logger.debug("auth response tracking skipped", exc_info=True)

    def record_nav_timeout(self):
        self._nav_timeout_count += 1
        logger.warning(f"nav timeout count={self._nav_timeout_count}")
        trigger = detect_timeout_trigger(self._nav_timeout_count)
        if trigger:
            self._takeover.request_takeover(trigger.reason, trigger.trigger)

    def reset_nav_timeout_count(self):
        self._nav_timeout_count = 0

    def record_element_failure(self, selector: str):
        self._element_failure_count[selector] = self._element_failure_count.get(selector, 0) + 1
        count = self._element_failure_count[selector]
        trigger = detect_element_failure_trigger(count)
        if trigger:
            self._takeover.request_takeover(trigger.reason, trigger.trigger)

    def reset_element_failures(self):
        self._element_failure_count.clear()


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    name = _INVALID_FILENAME_CHARS.sub("_", name).strip()
    return name or "download.bin"


def _unique_path(output_dir: Path, filename: str) -> Path:
    stem, dot, suffix = filename.rpartition(".")
    path = output_dir / filename
    counter = 1
    while path.exists():
        if dot:
            path = output_dir / f"{stem} ({counter}){dot}{suffix}"
        else:
            path = output_dir / f"{stem} ({counter})"
        counter += 1
    return path


def _append_manifest(output_dir: Path, entry: dict) -> None:
    manifest_file = output_dir / "downloads_manifest.json"
    entries: list = []
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries = data
        except (OSError, json.JSONDecodeError):
            entries = []
    entries.append(entry)
    manifest_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
