"""登录凭证测试数据构造（store / service / route 三个测试模块共用）。"""

from __future__ import annotations

from typing import Any

from schemas.login_credential import LoginCredentialSpec

WS = "ws-test"
SITE = "accounts.example.com"


def spec(**overrides: Any) -> LoginCredentialSpec:
    base: dict[str, Any] = {
        "site": SITE,
        "url": f"https://{SITE}/login",
        "username": "alice",
        "password": "s3cret",
    }
    base.update(overrides)
    return LoginCredentialSpec(**base)
