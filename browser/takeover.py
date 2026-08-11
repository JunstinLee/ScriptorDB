from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from core.logging_setup import get_logger

logger = get_logger("browser.takeover")


class HumanTakeoverState(str, Enum):
    RUNNING = "running"
    DETECTED = "detected"
    WAITING_HUMAN = "waiting_human"
    HUMAN_CONTROL = "human_control"
    RESUMING = "resuming"
    CANCELLED = "cancelled"


TAKEOVER_TIMEOUT = 150


class HumanTakeoverManager:
    def __init__(self):
        self.state = HumanTakeoverState.RUNNING
        self.reason: str = ""
        self.trigger: str = ""
        self.screenshot_path: str | None = None
        self.current_url: str = ""
        self.result: str = ""
        self._detected_at: float = 0
        self._wait_start: float = 0
        self._timeout_task: asyncio.Task | None = None
        self._on_timeout: Callable | None = None
        self.message: str = ""

    def can_agent_proceed(self) -> bool:
        return self.state in (HumanTakeoverState.RUNNING, HumanTakeoverState.RESUMING)

    def should_pause_agent(self) -> bool:
        return self.state == HumanTakeoverState.DETECTED

    def is_paused(self) -> bool:
        return self.state in (HumanTakeoverState.WAITING_HUMAN, HumanTakeoverState.HUMAN_CONTROL)

    def request_takeover(self, reason: str, trigger: str = "",
                         url: str = "", screenshot: str | None = None) -> bool:
        if self.state != HumanTakeoverState.RUNNING:
            return False
        self.state = HumanTakeoverState.DETECTED
        self.reason = reason
        self.trigger = trigger
        self.current_url = url
        self.screenshot_path = screenshot
        self._detected_at = datetime.now(timezone.utc).timestamp()
        logger.warning(f"takeover requested reason={reason} trigger={trigger} url={url}")
        return True

    def enter_waiting(self, on_timeout: Callable | None = None):
        self.state = HumanTakeoverState.WAITING_HUMAN
        self._wait_start = datetime.now(timezone.utc).timestamp()
        self._on_timeout = on_timeout
        logger.info("takeover enter waiting")
        if on_timeout:
            self._timeout_task = asyncio.create_task(self._timeout_loop())

    def enter_human_control(self):
        self._cancel_timeout()
        self.state = HumanTakeoverState.HUMAN_CONTROL
        self.message = "请在 Chrome 窗口中操作"
        logger.info("takeover enter human_control")

    def complete(self, result: str):
        self._cancel_timeout()
        self.state = HumanTakeoverState.RESUMING
        self.result = result
        logger.info(f"takeover complete result={result}")

    def cancel(self, reason: str = ""):
        self._cancel_timeout()
        self.state = HumanTakeoverState.CANCELLED
        logger.info(f"takeover cancelled reason={reason}")
        if reason:
            self.reason = reason

    def reset(self):
        self._cancel_timeout()
        self.state = HumanTakeoverState.RUNNING
        self.reason = ""
        self.trigger = ""
        self.screenshot_path = None
        self.result = ""
        self.message = ""
        self._detected_at = 0
        self._wait_start = 0

    def _cancel_timeout(self):
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None

    async def _timeout_loop(self):
        await asyncio.sleep(TAKEOVER_TIMEOUT)
        if self.state == HumanTakeoverState.WAITING_HUMAN:
            logger.warning(f"takeover timeout after {TAKEOVER_TIMEOUT}s")
            self.cancel(f"超时：{TAKEOVER_TIMEOUT}秒内无用户响应")
            if self._on_timeout:
                self._on_timeout()


@dataclass
class HumanTrigger:
    reason: str
    trigger: str
    confidence: float


async def _visible_match(evaluate, selector: str) -> bool:
    js = (
        "() => { const e = document.querySelector(%s); "
        "if (!e) return false; "
        "const s = getComputedStyle(e); "
        "const r = e.getBoundingClientRect(); "
        "return r.width > 0 && r.height > 0 "
        "&& s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0; }"
    ) % json.dumps(selector)
    try:
        return bool(await evaluate(js))
    except Exception:
        return False


async def detect_human_needed(page, *, evaluate=None) -> HumanTrigger | None:
    if page is None:
        return None
    if evaluate is None:
        evaluate = getattr(page, "evaluate", None)
    if evaluate is None:
        return None

    url = page.url
    title = ""
    try:
        title = (await page.title()).lower()
    except Exception:
        pass

    if await _visible_match(evaluate, '.g-recaptcha, iframe[src*="recaptcha"]'):
        return HumanTrigger("检测到 reCAPTCHA 验证码", "captcha", 1.0)

    if await _visible_match(evaluate, '.h-captcha, iframe[src*="hcaptcha"]'):
        return HumanTrigger("检测到 hCaptcha 验证码", "captcha", 1.0)

    if await _visible_match(
        evaluate,
        'iframe[src*="challenges.cloudflare.com"], [data-turnstile-sitekey], '
        'input[name="cf-turnstile-response"]',
    ):
        return HumanTrigger("检测到 Cloudflare Turnstile 验证码", "captcha", 0.9)

    if await _visible_match(
        evaluate,
        "img[id*=captcha], img[class*=captcha], img[src*=captcha], "
        "img[id*=verify], img[class*=verify]",
    ):
        return HumanTrigger("检测到图形验证码", "captcha", 0.9)

    mfa_queries = [
        "input[autocomplete='one-time-code']",
        "input[name*='otp']", "input[name*='totp']",
        "input[name*='mfa']", "input[name*='verification']",
        "input[type='tel'][maxlength='6']",
        "input[inputmode='numeric'][maxlength='6']",
    ]
    for q in mfa_queries:
        if await evaluate(f"() => !!document.querySelector({json.dumps(q)})"):
            return HumanTrigger(f"检测到多因素认证(MFA)输入框: {q}", "mfa", 0.95)

    oauth_patterns = [
        ("accounts.google.com/signin/oauth", "Google OAuth"),
        ("login.microsoftonline.com", "Microsoft OAuth"),
        ("github.com/login/oauth", "GitHub OAuth"),
    ]
    for pattern, name in oauth_patterns:
        if pattern in url:
            return HumanTrigger(f"检测到 {name} 授权页面", "oauth", 0.9)

    antibot_keywords = [
        "verify you are human", "are you a robot",
        "checking your browser", "ddos protection",
        "just a moment", "security check",
    ]
    for kw in antibot_keywords:
        if kw in title:
            return HumanTrigger(f"检测到反爬虫页面: {title}", "antibot", 0.95)

    if "cloudflare" in title and ("attention required" in title or "just a moment" in title):
        return HumanTrigger("检测到 Cloudflare 防护", "antibot", 0.95)

    if await evaluate(
        "() => { const e = document.querySelector('input[type=file]'); "
        "if (!e) return false; const r = e.getBoundingClientRect(); "
        "return r.width > 0 && r.height > 0; }"
    ):
        return HumanTrigger("检测到文件上传选择器", "file_upload", 0.7)

    if ("checkout" in url.lower() or "payment" in url.lower()):
        has_payment = await evaluate(
            "() => !!(document.querySelector('input[name*=card]') || "
            "document.querySelector('[data-testid=payment]'))"
        )
        if has_payment:
            return HumanTrigger("检测到支付确认页面", "payment", 0.8)

    login_keywords = ["sign in", "log in", "login", "signin"]
    if any(kw in title for kw in login_keywords):
        has_password = await evaluate(
            "() => !!document.querySelector('input[type=password]')"
        )
        if has_password:
            return HumanTrigger("检测到登录页面", "login", 0.75)

    return None


def detect_timeout_trigger(consecutive_timeout_count: int) -> HumanTrigger | None:
    if consecutive_timeout_count >= 3:
        return HumanTrigger(
            f"连续 {consecutive_timeout_count} 次导航超时，可能需要人工处理",
            "timeout", 0.8
        )
    return None


def detect_element_failure_trigger(same_selector_failure_count: int) -> HumanTrigger | None:
    if same_selector_failure_count >= 3:
        return HumanTrigger(
            f"同一元素操作连续失败 {same_selector_failure_count} 次",
            "element_failure", 0.7
        )
    return None
