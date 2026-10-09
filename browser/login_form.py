from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from browser.form_scan import extract_form_js
from browser.login_state import LoginPage, _login_page_signals
from core.logging_setup import get_logger

logger = get_logger("browser.login_form")

# 字段角色
ROLE_USERNAME = "username"
ROLE_PASSWORD = "password"
ROLE_OTP = "otp"
ROLE_UNKNOWN = "unknown"

# 分类关键词（OTP 与 browser/takeover.py 的 mfa_queries 对齐）
_OTP_HINTS = (
    "otp", "totp", "mfa", "verification", "yzm", "smscode",
    "验证码", "one-time-code", "authcode", "auth_code",
)
_USERNAME_HINTS = (
    "username", "user", "email", "account", "login", "loginname",
    "login_name", "identifier", "phone", "mobile", "手机号", "账号", "邮箱",
)
_PASSWORD_HINTS = ("password", "passwd", "pass", "密码")

# 提交按钮文本关键词
_SUBMIT_TEXT = (
    "login", "log in", "sign in", "signin", "sign-in", "submit",
    "登录", "登入", "继续", "next", "continue", "enter",
)

# 一次性 evaluate：遍历可见表单控件，返回结构化元数据（不含角色分类）。
# 有 <form> 时只遍历表单内控件，否则回退整个文档（JS 框架常见无 form 表单）。
# 扫描逻辑与 browser_read 表单读、点击快照共用，见 browser/form_scan.py。
_EXTRACT_FORM_JS = extract_form_js()


@dataclass
class LoginField:
    """登录页上的一个可填写控件。"""

    role: str
    selector: str
    tag: str = ""
    type: str = ""
    name: str = ""
    id: str = ""
    label: str = ""
    placeholder: str = ""
    autocomplete: str = ""
    required: bool = False
    in_form: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "selector": self.selector,
            "tag": self.tag,
            "type": self.type,
            "name": self.name,
            "id": self.id,
            "label": self.label,
            "placeholder": self.placeholder,
            "autocomplete": self.autocomplete,
            "required": self.required,
        }


@dataclass
class LoginFormInfo:
    """登录页表单的结构化描述。"""

    url: str
    is_login_page: bool
    fields: list[LoginField] = field(default_factory=list)
    submit: LoginField | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "is_login_page": self.is_login_page,
            "fields": [f.to_dict() for f in self.fields],
            "submit": self.submit.to_dict() if self.submit else None,
        }

    def signature(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """去重签名：URL + 字段角色/选择器序列。"""
        return (
            self.url,
            tuple((f.role, f.selector) for f in self.fields),
        )


def _classify_role(raw: dict[str, Any]) -> str:
    """按优先级分类：type → autocomplete → name/id/placeholder/label 关键词。"""
    ftype = str(raw.get("type") or "").lower()
    if ftype == "password":
        return ROLE_PASSWORD
    autocomplete = str(raw.get("autocomplete") or "").lower()
    if autocomplete in ("username", "email", "user", "tel"):
        return ROLE_USERNAME
    if autocomplete in ("current-password", "new-password"):
        return ROLE_PASSWORD
    if autocomplete == "one-time-code":
        return ROLE_OTP
    text = " ".join((
        str(raw.get("name") or ""),
        str(raw.get("id") or ""),
        str(raw.get("placeholder") or ""),
        str(raw.get("label") or ""),
    )).lower()
    if any(h in text for h in _OTP_HINTS):
        return ROLE_OTP
    if any(h in text for h in _PASSWORD_HINTS):
        return ROLE_PASSWORD
    if any(h in text for h in _USERNAME_HINTS):
        return ROLE_USERNAME
    return ROLE_UNKNOWN


def _is_submit(raw: dict[str, Any]) -> bool:
    """提交按钮判定：input[type=submit/button/image] 或按钮文本含关键词。"""
    tag = str(raw.get("tag") or "").lower()
    ftype = str(raw.get("type") or "").lower()
    if tag == "input" and ftype in ("submit", "button", "image"):
        return True
    if tag == "button" and ftype in ("submit", ""):
        return True
    if tag == "button" and ftype == "button":
        text = str(raw.get("text") or "").lower()
        return any(k in text for k in _SUBMIT_TEXT)
    return False


def _build_field(raw: dict[str, Any], role: str) -> LoginField:
    return LoginField(
        role=role,
        selector=str(raw.get("selector") or ""),
        tag=str(raw.get("tag") or ""),
        type=str(raw.get("type") or ""),
        name=str(raw.get("name") or ""),
        id=str(raw.get("id") or ""),
        label=str(raw.get("label") or ""),
        placeholder=str(raw.get("placeholder") or ""),
        autocomplete=str(raw.get("autocomplete") or ""),
        required=bool(raw.get("required")),
        in_form=bool(raw.get("in_form", True)),
    )


async def extract_login_form(page: LoginPage) -> LoginFormInfo | None:
    """检测登录页并提取字段结构；非登录页或提取失败返回 None。"""
    is_login, _ = await _login_page_signals(page)
    if not is_login:
        logger.info("login form: 非登录页信号 url=%s", page.url)
        return None
    try:
        raw_controls = await page.evaluate(_EXTRACT_FORM_JS)
    except Exception as e:
        logger.debug("login form extraction failed: %s", e)
        return None
    if not isinstance(raw_controls, list):
        logger.warning("login form: evaluate 未返回列表 url=%s", page.url)
        return None

    fields: list[LoginField] = []
    submit: LoginField | None = None
    for raw in raw_controls:
        if not isinstance(raw, dict) or not raw.get("visible"):
            continue
        if _is_submit(raw):
            if submit is None:
                submit = _build_field(raw, ROLE_UNKNOWN)
            continue
        fields.append(_build_field(raw, _classify_role(raw)))

    info = LoginFormInfo(
        url=page.url,
        is_login_page=True,
        fields=fields,
        submit=submit,
    )
    logger.info(
        "login form extracted url=%s fields=%d submit=%s roles=%s selectors=%s",
        page.url, len(fields), submit.selector if submit else None,
        [f.role for f in fields],
        [f.selector for f in fields],
    )
    return info


_ROLE_NAMES = {
    ROLE_USERNAME: "Username/Email",
    ROLE_PASSWORD: "Password",
    ROLE_OTP: "Verification code/OTP",
    ROLE_UNKNOWN: "Other field",
}


def format_login_form_message(info: LoginFormInfo) -> str:
    """把表单信息格式化为注入对话的说明（AI 无需调用工具即可填表）。"""
    lines = [f"Login page detected ({info.url}); form fields were extracted automatically:"]
    for f in info.fields:
        hint = " ".join(x for x in (f.label, f.placeholder, f.name) if x)
        line = f"- {_ROLE_NAMES.get(f.role, f.role)}: selector={f.selector}"
        if hint:
            line += f" ({hint})"
        if f.required:
            line += " [required]"
        lines.append(line)
    if info.submit:
        lines.append(f"- Submit button: selector={info.submit.selector}")
    else:
        lines.append("- No submit button found")
    return "\n".join(lines)
