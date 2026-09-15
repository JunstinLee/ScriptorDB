from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence
from urllib.parse import urlparse

from playwright.async_api import Cookie

from core.logging_setup import get_logger

logger = get_logger("browser.login_state")

LoginStatus = Literal["logged_in", "logged_out", "unknown"]


class _CookieJar(Protocol):
    """检测所需的最小 cookie 接口（Page.context 满足）。"""

    async def cookies(self, urls: list[str] | None = None) -> Any: ...


class LoginPage(Protocol):
    """登录状态检测所需的最小页面接口。

    结构子类型：真实 playwright Page 天然满足；测试可传轻量 fake 实现，
    无需继承 Page。
    """

    @property
    def url(self) -> str: ...

    @property
    def context(self) -> _CookieJar: ...

    async def title(self) -> str: ...

    async def evaluate(self, expression: str, arg: Any = None) -> Any: ...

# URL 路径/哈希路由中的登录关键词（信号之一，不单独定论）
_LOGIN_URL_KEYWORDS = (
    "/login",
    "/signin",
    "/sign-in",
    "/log-in",
    "/auth/login",
    "/accounts/login",
    "/sessions/login",
)
# 标题登录关键词（中英双语）：中文站点标题含「登录」而无英文
LOGIN_TITLE_KEYWORDS = (
    "sign in", "log in", "login", "signin", "logon",
    "登录", "登入",
)
# 表单级登录语义关键词：中文站点标题常只写机构名/品牌名，线索在提交按钮文本上
_LOGIN_ACTION_KEYWORDS = (
    "login", "log in", "sign in", "signin", "sign-in",
    "登录", "登入",
)
_PASSWORD_INPUT_JS = "() => !!document.querySelector('input[type=password]')"
_LOGIN_ACTION_JS = """() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0
      && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const hints = %s;
  const hit = (t) => hints.some((h) => (t || '').toLowerCase().includes(h));
  const nodes = document.querySelectorAll(
    'button, input[type=submit], input[type=button], a[role=button]');
  for (const el of nodes) {
    if (!visible(el)) continue;
    if (hit(el.textContent) || hit(el.value) || hit(el.getAttribute('aria-label'))) {
      return true;
    }
  }
  const labels = document.querySelectorAll('form label, form legend');
  for (const el of labels) {
    if (visible(el) && hit(el.textContent)) return true;
  }
  return false;
}""" % json.dumps(list(_LOGIN_ACTION_KEYWORDS), ensure_ascii=False)


@dataclass
class LoginState:
    status: LoginStatus = "unknown"
    domain: str = ""
    reason: str = ""
    on_login_page: bool = False
    session_cookies: list[str] = field(default_factory=list)
    expected_cookie_names: list[str] = field(default_factory=list)


def netloc_of(url: str) -> str:
    """从 URL 提取规范化域名（去 userinfo/端口、小写）。"""
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return ""
    netloc = netloc.split("@")[-1]
    if ":" in netloc:
        netloc = netloc.rsplit(":", 1)[0]
    return netloc.lower()


def _is_login_url(url: str) -> bool:
    """URL 路径或哈希路由指向登录路径（覆盖 SPA 的 #/login）。"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    target = f"{parsed.path} {parsed.fragment}".lower()
    return any(kw in target for kw in _LOGIN_URL_KEYWORDS)


async def _has_password_input(page: LoginPage) -> bool:
    try:
        return bool(await page.evaluate(_PASSWORD_INPUT_JS))
    except Exception:
        return False


async def _has_login_action(page: LoginPage) -> bool:
    """表单级登录语义：可见提交按钮/label 文本含登录关键词。"""
    try:
        return bool(await page.evaluate(_LOGIN_ACTION_JS))
    except Exception:
        return False


async def _login_page_signals(page: LoginPage) -> tuple[bool, str]:
    """返回 (是否登录页, 证据)。

    信号：URL 指向登录路径，或「存在密码框」且（标题含登录关键词
    或表单含登录操作）。中英双语，覆盖中文站点——这类页面标题常只
    写机构名/品牌名，登录线索在提交按钮文本上。
    """
    if _is_login_url(page.url):
        return True, "URL 指向登录路径"
    if not await _has_password_input(page):
        return False, ""
    try:
        title = (await page.title()) or ""
    except Exception:
        title = ""
    if any(kw in title.lower() for kw in LOGIN_TITLE_KEYWORDS):
        return True, "页面标题含登录关键词且存在密码输入框"
    if await _has_login_action(page):
        return True, "存在密码输入框且表单含登录操作"
    return False, ""


async def _cookies_for_domain(page: LoginPage, domain: str) -> Sequence[Cookie]:
    if not domain:
        return []
    try:
        urls = [f"https://{domain}/", f"http://{domain}/"]
        return list(await page.context.cookies(urls=urls))
    except Exception as e:
        logger.warning("login_state: cookies fetch failed domain=%s err=%s", domain, e)
        return []


async def detect_login_state(
    page: LoginPage,
    domain: str | None = None,
    expected_cookie_names: list[str] | None = None,
) -> LoginState:
    """检测当前浏览器会话在指定域名的登录状态。

    - `expected_cookie_names`：保存登录态时存在的 cookie 名（来自 profile 的
      storage_state）。这是最强的信号——登录失效时这些 cookie 会缺失。
    - 无预期 cookie 时退化为启发式：登录页信号（URL/标题+密码框）、
      域名 cookie 存在性。
    """
    current_url = getattr(page, "url", "") or ""
    domain = domain or netloc_of(current_url)
    if not domain:
        logger.info("login state: 无有效域名 url=%s", current_url or "about:blank")
        return LoginState(
            status="unknown",
            domain="",
            reason="当前页面无有效域名（about:blank 等）",
        )

    cookies = await _cookies_for_domain(page, domain)
    cookie_names = [c.get("name", "") for c in cookies if c.get("name")]
    on_login_page, login_evidence = await _login_page_signals(page)

    if expected_cookie_names:
        present = [n for n in expected_cookie_names if n in cookie_names]
        state = LoginState(
            domain=domain,
            on_login_page=on_login_page,
            session_cookies=cookie_names,
            expected_cookie_names=list(expected_cookie_names),
        )
        if present:
            state.status = "logged_in"
            state.reason = f"保存的会话 cookie 仍存在 ({len(present)}/{len(expected_cookie_names)})"
        else:
            state.status = "logged_out"
            state.reason = "保存的会话 cookie 已全部缺失，登录态已失效"
        logger.info(
            "login state: 会话 cookie 判定 domain=%s status=%s on_login_page=%s present=%d/%d cookies=%s",
            domain, state.status, on_login_page, len(present), len(expected_cookie_names), cookie_names,
        )
        return state

    if on_login_page:
        logger.info(
            "login state: 登录页信号判定 domain=%s status=logged_out on_login_page=True evidence=%s cookies=%s",
            domain, login_evidence, cookie_names,
        )
        return LoginState(
            status="logged_out",
            domain=domain,
            reason=login_evidence,
            on_login_page=True,
            session_cookies=cookie_names,
        )

    if cookie_names:
        logger.info(
            "login state: 域名 cookie 判定 domain=%s status=logged_in on_login_page=False cookies=%s",
            domain, cookie_names,
        )
        return LoginState(
            status="logged_in",
            domain=domain,
            reason=f"存在 {len(cookie_names)} 个域名 cookie",
            session_cookies=cookie_names,
        )

    logger.info("login state: 无法判定 domain=%s status=unknown on_login_page=False cookies=%s", domain, cookie_names)
    return LoginState(
        status="unknown",
        domain=domain,
        reason="无 cookie 且不在登录页，需访问受保护页面确认",
    )
