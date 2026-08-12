from __future__ import annotations

from types import SimpleNamespace

from browser.takeover import detect_human_needed


class FakePage:
    def __init__(self, url: str = "", title: str = "", results: dict[str, bool] | None = None):
        self.url = url
        self._title = title
        self.results = results or {}

    async def title(self):
        return self._title

    async def evaluate(self, js: str):
        for key, result in self.results.items():
            if key in js:
                return result
        return False


async def test_page_none_returns_none():
    assert await detect_human_needed(None) is None


async def test_no_threats_returns_none():
    page = FakePage(title="Oracle - Investor Relations - SEC Filings")
    assert await detect_human_needed(page) is None


async def test_hidden_captcha_image_ignored():
    page = FakePage(
        title="Oracle - Investor Relations - SEC Filings",
        results={"img[id*=captcha]": False},
    )
    assert await detect_human_needed(page) is None


async def test_visible_captcha_image_triggers():
    page = FakePage(
        title="Oracle - Investor Relations - SEC Filings",
        results={"img[id*=captcha]": True},
    )
    trigger = await detect_human_needed(page)
    assert trigger is not None
    assert trigger.trigger == "captcha"
    assert trigger.reason == "检测到图形验证码"


async def test_hidden_recaptcha_ignored():
    page = FakePage(title="Some page", results={"recaptcha": False})
    assert await detect_human_needed(page) is None


async def test_visible_recaptcha_triggers():
    page = FakePage(title="Some page", results={"recaptcha": True})
    trigger = await detect_human_needed(page)
    assert trigger is not None
    assert trigger.trigger == "captcha"
    assert trigger.reason == "检测到 reCAPTCHA 验证码"


async def test_visible_hcaptcha_triggers():
    page = FakePage(title="Some page", results={"hcaptcha": True})
    trigger = await detect_human_needed(page)
    assert trigger is not None
    assert trigger.trigger == "captcha"
    assert trigger.reason == "检测到 hCaptcha 验证码"


async def test_hidden_turnstile_ignored():
    page = FakePage(title="Some page", results={"challenges.cloudflare.com": False})
    assert await detect_human_needed(page) is None


async def test_visible_turnstile_triggers():
    page = FakePage(title="Some page", results={"challenges.cloudflare.com": True})
    trigger = await detect_human_needed(page)
    assert trigger is not None
    assert trigger.trigger == "captcha"
    assert trigger.reason == "检测到 Cloudflare Turnstile 验证码"


async def test_login_page_with_visible_password_triggers():
    page = FakePage(
        title="Sign in to My Account",
        results={"input[type=password]": True},
    )
    trigger = await detect_human_needed(page)
    assert trigger is not None
    assert trigger.trigger == "login"


async def test_login_title_without_password_ignored():
    page = FakePage(
        title="Sign in to My Account",
        results={"input[type=password]": False},
    )
    assert await detect_human_needed(page) is None


async def test_injected_evaluate_used():
    page = SimpleNamespace(url="", title=lambda: _resolved("Some page"))
    called: list[str] = []

    async def fake_evaluate(js: str):
        called.append(js)
        return "img[id*=captcha]" in js

    trigger = await detect_human_needed(page, evaluate=fake_evaluate)
    assert trigger is not None
    assert trigger.trigger == "captcha"
    assert called


async def _resolved(value):
    return value
