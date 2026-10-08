"""人工接管触发检测（从 browser/takeover.py 原样搬移）。

只含「页面是否需要人工介入」的启发式探测：验证码 / MFA / OAuth / 反爬 /
文件上传 / 支付 / 扫码登录，以及连续失败与超时的计数触发器。状态机仍在
:mod:`browser.takeover`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from browser.login_state import LOGIN_TITLE_KEYWORDS


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
        return HumanTrigger("reCAPTCHA detected", "captcha", 1.0)

    if await _visible_match(evaluate, '.h-captcha, iframe[src*="hcaptcha"]'):
        return HumanTrigger("hCaptcha detected", "captcha", 1.0)

    if await _visible_match(
        evaluate,
        'iframe[src*="challenges.cloudflare.com"], [data-turnstile-sitekey], '
        'input[name="cf-turnstile-response"]',
    ):
        return HumanTrigger("Cloudflare Turnstile detected", "captcha", 0.9)

    if await _visible_match(
        evaluate,
        "img[id*=captcha], img[class*=captcha], img[src*=captcha], "
        "img[id*=verify], img[class*=verify]",
    ):
        return HumanTrigger("Image captcha detected", "captcha", 0.9)

    # 中文图形验证码：国产验证码组件可见标记
    cn_captcha_components = [
        ".geetest_panel, .geetest_holder, .geetest_slide",
        "[id*=yidun], [class*=yidun]",
        'iframe[id*=tcaptcha], [class*=tcaptcha]',
        "[class*=aliyunCaptcha], #nc_1_wrapper",
    ]
    for selector in cn_captcha_components:
        if await _visible_match(evaluate, selector):
            return HumanTrigger("Image captcha detected", "captcha", 0.9)

    # 中文图形验证码：图片类标记（yzm / checkcode）
    if await _visible_match(
        evaluate,
        "img[id*=yzm], img[class*=yzm], img[src*=yzm], "
        "img[src*=checkcode], img[class*=checkcode]",
    ):
        return HumanTrigger("Image captcha detected", "captcha", 0.85)

    # 中文图形验证码：标题关键词
    for kw in ["安全验证", "人机验证", "拖动滑块"]:
        if kw in title:
            return HumanTrigger("Image captcha detected", "captcha", 0.85)

    mfa_queries = [
        "input[autocomplete='one-time-code']",
        "input[name*='otp']", "input[name*='totp']",
        "input[name*='mfa']", "input[name*='verification']",
        "input[name*='yzm']", "input[name*='smscode']",
        "input[placeholder*='验证码']",
        "input[type='tel'][maxlength='6']",
        "input[inputmode='numeric'][maxlength='6']",
    ]
    for q in mfa_queries:
        if await evaluate(f"() => !!document.querySelector({json.dumps(q)})"):
            return HumanTrigger(f"MFA input detected: {q}", "mfa", 0.95)

    oauth_patterns = [
        ("accounts.google.com/signin/oauth", "Google OAuth"),
        ("login.microsoftonline.com", "Microsoft OAuth"),
        ("github.com/login/oauth", "GitHub OAuth"),
    ]
    for pattern, name in oauth_patterns:
        if pattern in url:
            return HumanTrigger(f"{name} authorization page detected", "oauth", 0.9)

    # 国内 SSO / 授权 URL 通用规则（精确域名表之后）
    url_lower = url.lower()
    if any(marker in url_lower for marker in ("oauth", "sso", "/cas/login")):
        return HumanTrigger("Third-party login/SSO authorization page detected", "oauth", 0.7)

    antibot_keywords = [
        "verify you are human", "are you a robot",
        "checking your browser", "ddos protection",
        "just a moment", "security check",
    ]
    for kw in antibot_keywords:
        if kw in title:
            return HumanTrigger(f"Anti-bot page detected: {title}", "antibot", 0.95)

    if "cloudflare" in title and ("attention required" in title or "just a moment" in title):
        return HumanTrigger("Cloudflare protection detected", "antibot", 0.95)

    if await evaluate(
        "() => { const e = document.querySelector('input[type=file]'); "
        "if (!e) return false; const r = e.getBoundingClientRect(); "
        "return r.width > 0 && r.height > 0; }"
    ):
        return HumanTrigger("File upload dialog detected", "file_upload", 0.7)

    if ("checkout" in url.lower() or "payment" in url.lower()):
        has_payment = await evaluate(
            "() => !!(document.querySelector('input[name*=card]') || "
            "document.querySelector('[data-testid=payment]'))"
        )
        if has_payment:
            return HumanTrigger("Payment confirmation page detected", "payment", 0.8)

    # 扫码登录：登录特征 + 无密码框 + 二维码可见
    login_feature = any(kw in title for kw in LOGIN_TITLE_KEYWORDS) or any(
        marker in url_lower for marker in ("login", "signin", "登录", "登入")
    )
    if login_feature:
        has_password = await evaluate(
            "() => !!document.querySelector('input[type=password]')"
        )
        if not has_password:
            qr_seen = await evaluate(
                "() => { const q = document.querySelector('img[src*=qrcode]'); "
                "if (q) { const r = q.getBoundingClientRect(); "
                "if (r.width > 0 && r.height > 0) return true; } "
                "const c = document.querySelector('canvas'); "
                "if (c) { const r = c.getBoundingClientRect(); "
                "if (r.width > 0 && r.height > 0) return true; } "
                "return !!(document.body && document.body.innerText.includes('扫码')); }"
            )
            if qr_seen:
                return HumanTrigger("QR code login page detected; scan the code to sign in", "qrcode", 0.85)

    if any(kw in title for kw in LOGIN_TITLE_KEYWORDS):
        has_password = await evaluate(
            "() => !!document.querySelector('input[type=password]')"
        )
        if has_password:
            return HumanTrigger("Login page detected", "login", 0.75)

    return None


def detect_timeout_trigger(consecutive_timeout_count: int) -> HumanTrigger | None:
    if consecutive_timeout_count >= 3:
        return HumanTrigger(
            f"{consecutive_timeout_count} consecutive navigation timeouts — manual action may be needed",
            "timeout", 0.8
        )
    return None


def detect_element_failure_trigger(same_selector_failure_count: int) -> HumanTrigger | None:
    if same_selector_failure_count >= 3:
        return HumanTrigger(
            f"Same element failed {same_selector_failure_count} times in a row",
            "element_failure", 0.7
        )
    return None
