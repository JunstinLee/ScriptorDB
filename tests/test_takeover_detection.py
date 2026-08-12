from __future__ import annotations

from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize(
    ("url", "title", "results", "expected"),
    [
        ("", "Oracle - Investor Relations - SEC Filings", {}, None),
        ("", "Oracle - Investor Relations - SEC Filings", {"img[id*=captcha]": False}, None),
        ("", "Oracle - Investor Relations - SEC Filings", {"img[id*=captcha]": True}, ("captcha", "检测到图形验证码")),
        ("", "Some page", {"recaptcha": False}, None),
        ("", "Some page", {"recaptcha": True}, ("captcha", "检测到 reCAPTCHA 验证码")),
        ("", "Some page", {"hcaptcha": True}, ("captcha", "检测到 hCaptcha 验证码")),
        ("", "Some page", {"challenges.cloudflare.com": False}, None),
        ("", "Some page", {"challenges.cloudflare.com": True}, ("captcha", "检测到 Cloudflare Turnstile 验证码")),
        ("", "Sign in to My Account", {"input[type=password]": True}, ("login", "检测到登录页面")),
        ("", "Sign in to My Account", {"input[type=password]": False}, None),
        ("https://accounts.google.com/signin/oauth", "Some page", {}, ("oauth", "检测到 Google OAuth 授权页面")),
        ("https://login.microsoftonline.com/xyz", "Some page", {}, ("oauth", "检测到 Microsoft OAuth 授权页面")),
        ("", "Checking your browser before accessing", {}, ("antibot", "检测到反爬虫页面")),
        ("", "Cloudflare attention required", {}, ("antibot", "检测到 Cloudflare 防护")),
    ],
)
async def test_detect_combinations(url, title, results, expected):
    page = FakePage(url=url, title=title, results=results)
    trigger = await detect_human_needed(page)
    if expected is None:
        assert trigger is None
    else:
        assert trigger is not None
        assert trigger.trigger == expected[0]
        assert expected[1] in trigger.reason


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
