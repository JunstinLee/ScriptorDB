from __future__ import annotations

from typing import Any

from browser.login_state import netloc_of
from config.credential_store import get_site_credential
from runtime.redact import register_password

# 判定元素是否密码控件：只读 type/autocomplete，绝不读 value。
_PASSWORD_CONTROL_JS = """el => {
    if (!el || el.nodeType !== 1) return false;
    const tag = (el.tagName || '').toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const auto = (el.getAttribute('autocomplete') || '').toLowerCase();
    return (tag === 'input' && type === 'password')
        || auto === 'current-password'
        || auto === 'new-password';
}"""


async def is_password_control(page: Any, selector: str) -> bool:
    """判定 selector 首元素是否为密码控件；异常/不存在返回 False。

    只读 type/autocomplete，不触碰 value。调用方据此决定是否拦截读取。
    """
    try:
        element = await page.query_selector(selector)
    except Exception:
        return False
    if element is None:
        return False
    try:
        return bool(await element.evaluate(_PASSWORD_CONTROL_JS))
    except Exception:
        return False


def current_site_password(
    page_url: str | None,
    workspace_id: str | None,
) -> str | None:
    """取当前页面对应站点的系统密码并登记；取不到返回 None。

    workspace_id/url 缺失、无凭证、password 空 → None（调用方按放行处理）。
    """
    if not page_url or not workspace_id:
        return None
    site = netloc_of(page_url)
    if not site:
        return None
    cred = get_site_credential(workspace_id, site)
    if not cred:
        return None
    password = cred.get("password") or ""
    if not password:
        return None
    register_password(password)
    return password
