from __future__ import annotations

"""自动填写服务：站点识别 → 读系统凭证 → 普通代码填表单（非 AI）。

验证码（otp 字段）不由代码填写：发现 otp 字段时只填完长凭证并返回
`manual_otp_guided`，由 takeover hook 的决策层引导用户到真实 Chrome 窗口
手动输入。本模块不触碰 takeover manager（不调 reset/request_takeover/
enter_waiting），只产出决策，编排由 runtime/runner/takeover_hook.py 统一执行。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from browser.login_form import (
    ROLE_OTP,
    ROLE_PASSWORD,
    ROLE_UNKNOWN,
    ROLE_USERNAME,
    LoginField,
    LoginFormInfo,
)
from browser.login_state import netloc_of
from config.credential_store import get_site_credential
from core.logging_setup import get_logger
from schemas.login_flow import LoginFlowStatus

logger = get_logger("browser.autofill")

# 与 browser/login_form.py 的 _USERNAME_HINTS 对齐的账号语义关键词
# （用于 ROLE_UNKNOWN 字段的语义名回退，需避开 password/otp 字段）。
_USERNAME_HINTS = (
    "username", "user", "email", "account", "login", "loginname",
    "login_name", "identifier", "phone", "mobile", "手机号", "账号", "邮箱",
)

# 可填控件 type 白名单（input 除按钮类外均可填）
_UNFILLABLE_INPUT_TYPES = {
    "button", "submit", "image", "reset", "hidden",
    "checkbox", "radio", "file",
}
# 兜底 username 的可填 input type（无账号角色字段时）
_TEXT_INPUT_TYPES = {"", "text", "email", "tel", "search", "url", "number"}

# 图片验证码输入框特征（无 otp 分类但绝不可自动填——纯图形码由接管引导人工）
_CAPTCHA_HINTS = ("captcha", "checkcode", "verifycode")

# 附加信息匹配的稳定特征键（与 01 MatchHints 一致）
_HINT_KEYS = ("name", "id", "label", "placeholder")


def _norm(text: str) -> str:
    """归一化用于比较：小写 + 去空白。"""
    return re.sub(r"\s+", "", (text or "").lower())


def _field_text(field: LoginField) -> str:
    return " ".join(x for x in (field.name, field.id, field.label, field.placeholder) if x)


def _is_fillable(field: LoginField) -> bool:
    """控件是否可被普通代码可靠填写。

    select/textarea 可填；input 除按钮/checkbox/radio/file/hidden 外可填。
    """
    tag = (field.tag or "").lower()
    if tag in ("select", "textarea"):
        return True
    if tag != "input":
        return False
    return (field.type or "").lower() not in _UNFILLABLE_INPUT_TYPES


def _is_otp_field(field: LoginField) -> bool:
    """只信任已分类为 otp 的字段（图片验证码等无 otp 特征的不属于候选）。"""
    return field.role == ROLE_OTP


def _is_captcha_field(field: LoginField) -> bool:
    """图片验证码输入框（英文 captcha/checkcode 特征，未被打成 otp 角色）。"""
    if _is_otp_field(field):
        return True
    text = _norm(_field_text(field))
    return any(_norm(h) in text for h in _CAPTCHA_HINTS)


def _is_checkbox_radio(field: LoginField) -> bool:
    return (field.tag or "").lower() == "input" and (field.type or "").lower() in (
        "checkbox", "radio",
    )


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    t = _norm(text)
    return any(_norm(h) in t for h in hints)


@dataclass
class AutofillDecision:
    """autofill 的接管决策（纯数据，不触碰 takeover manager）。

    - `kind == "reset"`: fill_ok 且无 otp → 清掉登录页误触发的接管，agent 继续。
    - `kind == "pause"`: 需要人工挂起（未配置 / otp 引导 / 填失败）。
    - `kind == "none"`: 无动作，走原 detect_takeover 触发路径。
    - `override_reason`: pause 时是否用 `reason`/`trigger` 覆盖接管值
      （otp 引导 / 填失败文案）；为 False 时保留检测阶段的值（未配置走默认文案）。
    """

    kind: Literal["none", "reset", "pause"] = "none"
    override_reason: bool = False
    reason: str = ""
    trigger: str = ""


@dataclass
class AutofillResult:
    """一次自动填写的完整结果（含状态 + 决策）。"""

    status: LoginFlowStatus
    decision: AutofillDecision = field(default_factory=AutofillDecision)


# ---- 填充原语 ------------------------------------------------------------------


async def _locator_value(page, selector: str) -> str:
    """读取当前控件值（幂等判据）；失败返回空串。"""
    try:
        locator = page.locator(selector)
        if await locator.count() == 0:
            return ""
        if await locator.evaluate(
            "(el) => el.tagName && el.tagName.toLowerCase() === 'select'"
        ):
            return await locator.input_value()
        return await locator.input_value()
    except Exception:
        return ""


async def _fill_control(page, field: LoginField, value: str) -> str:
    """按控件类型填充单个字段。成功返回 ""，失败返回错误描述。

    checkbox/radio 不进匹配候选（由调用方保证），这里防御性跳过。
    """
    tag = (field.tag or "").lower()
    if _is_checkbox_radio(field):
        return "checkbox/radio controls are not filled"
    selector = field.selector
    if not selector:
        return "no selector"
    locator = page.locator(selector)
    try:
        if tag == "select":
            await locator.select_option(value)
            return ""
        await locator.fill(value)
        return ""
    except Exception as e:
        return f"{type(e).__name__}: {e}"


async def _fill_if_empty(page, field: LoginField, value: str) -> str:
    """幂等填充：槽位非空则跳过（重复执行安全，不重填用户已输入的值）。"""
    if await _locator_value(page, field.selector):
        return ""
    return await _fill_control(page, field, value)


# ---- 槽位 → 字段映射 ------------------------------------------------------------


def _match_username_field(fields: list[LoginField]) -> LoginField | None:
    """username 槽位匹配：① role=username；② unknown 语义名回退；③ 兜底 text 字段。"""
    for f in fields:
        if f.role == ROLE_USERNAME:
            return f
    for f in fields:
        if f.role == ROLE_UNKNOWN and _contains_any(_field_text(f), _USERNAME_HINTS):
            if not _is_otp_field(f) and f.role != ROLE_PASSWORD:
                return f
    for f in fields:
        if f.tag == "input" and (f.type or "").lower() in _TEXT_INPUT_TYPES:
            if f.role not in (ROLE_PASSWORD, ROLE_OTP) and not _is_captcha_field(f):
                return f
    return None


def _match_password_field(fields: list[LoginField]) -> LoginField | None:
    """password 槽位：仅 role=password 的字段（无则无法填）。"""
    for f in fields:
        if f.role == ROLE_PASSWORD:
            return f
    return None


def _exact_hint_match(field: LoginField, hints: dict) -> bool:
    """稳定特征精确匹配：field 的 name/id/label/placeholder 与保存时 hints 对应相等。"""
    for key in _HINT_KEYS:
        saved = (hints or {}).get(key)
        if not saved:
            continue
        actual = getattr(field, key, "") or ""
        if _norm(saved) == _norm(actual):
            return True
    return False


def _semantic_match(field: LoginField, field_label: str) -> bool:
    """语义名双向子串匹配（保存时无 match_hints 也能命中）。"""
    label = _norm(field_label)
    if not label:
        return False
    text = _norm(_field_text(field))
    if not text:
        return False
    return label in text or text in label


def _keyword_match(field: LoginField, field_label: str) -> bool:
    """field_label 拆词（user/id/account…）与候选字段文本匹配。"""
    words = [w for w in re.split(r"[^a-z0-9\u4e00-\u9fff]+", field_label.lower()) if w]
    if not words:
        return False
    text = _norm(_field_text(field))
    return any(_norm(w) in text for w in words)


def _match_extra_field(
    fields: list[LoginField],
    used_selectors: set[str],
    extra: dict,
) -> tuple[LoginField | None, str]:
    """extra（附加登录信息）匹配。

    候选池 = 可填写字段 - otp - 已占用的 username/password 字段；
    优先级：① match_hints 稳定特征 → ② field_label 语义名 → ③ 拆词关键词
    → ④ 仅当候选唯一时用保存的 selector（宁缺毋错）。

    返回 (命中的字段 or None, 错误描述 or "")。
    """
    candidates = [
        f for f in fields
        if f.role != ROLE_OTP
        and f.selector not in used_selectors
        and _is_fillable(f)
        and not _is_captcha_field(f)
    ]
    if not candidates:
        return None, ""

    hints = extra.get("match_hints") if isinstance(extra, dict) else None
    if isinstance(hints, dict):
        for f in candidates:
            if _exact_hint_match(f, hints):
                return f, ""
        # hints 落空：继续按 field_label 语义/关键词回退

    field_label = str(extra.get("field_label") or "") if isinstance(extra, dict) else ""
    for f in candidates:
        if _semantic_match(f, field_label):
            return f, ""
    for f in candidates:
        if _keyword_match(f, field_label):
            return f, ""

    # 最后才 selector：仅当候选唯一（selector 最易变，多候选时不可靠）
    if len(candidates) == 1:
        saved_selector = str((hints or {}).get("selector") or "")
        if saved_selector and saved_selector == candidates[0].selector:
            return candidates[0], ""
        return candidates[0], ""
    return None, "extra field not uniquely matchable"


# ---- 状态构造与决策 --------------------------------------------------------------


def _build_status(
    site: str,
    configured: bool,
    *,
    username_filled: bool = False,
    password_filled: bool = False,
    extra_required: bool = False,
    extra_filled: bool = False,
    needs_otp: bool = False,
    manual_otp_guided: bool = False,
    fill_ok: bool = False,
    fill_error: str = "",
) -> LoginFlowStatus:
    return LoginFlowStatus(
        site=site,
        login_form_detected=True,
        configured=configured,
        username_filled=username_filled,
        password_filled=password_filled,
        extra_required=extra_required,
        extra_filled=extra_filled,
        needs_otp=needs_otp,
        manual_otp_guided=manual_otp_guided,
        fill_ok=fill_ok,
        fill_error=fill_error,
    )


def decide_takeover(status: LoginFlowStatus) -> AutofillDecision:
    """由登录状态推导接管决策（纯函数，不触碰 takeover manager）。"""
    if not status.login_form_detected:
        return AutofillDecision(kind="none")

    # 已配置且填完、无 otp：清掉登录页误触发的接管，agent 继续原逻辑
    if status.fill_ok and not status.needs_otp:
        return AutofillDecision(kind="reset")

    # 已配置、长凭证填完、发现 otp：引导用户在 Chrome 手动输验证码
    if status.manual_otp_guided:
        return AutofillDecision(
            kind="pause",
            override_reason=True,
            reason="Credentials were filled. Enter the verification code in the Chrome window, then press Finish.",
            trigger="mfa",
        )

    # 已配置但填失败：覆盖为错误文案（不误填、提示人工处理）
    if status.configured and status.fill_error:
        return AutofillDecision(
            kind="pause",
            override_reason=True,
            reason=f"Auto-fill failed: {status.fill_error}. Complete the form in the Chrome window.",
            trigger="autofill_error",
        )

    # 未配置 / 其余阻塞：需要人工（走既有接管默认文案，不覆盖 reason/trigger）
    return AutofillDecision(kind="pause")


# ---- 主入口 ---------------------------------------------------------------------


async def autofill_login_form(
    page: Any,
    info: LoginFormInfo,
    cred: dict | None,
) -> AutofillResult:
    """对已提取的登录表单执行自动填写，返回状态 + 接管决策。

    - cred=None（未配置）：不填任何字段。
    - 只信任已分类字段；otp 字段留空、绝不触碰。
    - 幂等：已填（input_value 非空）的槽位跳过。
    """
    site = netloc_of(info.url)
    if cred is None:
        status = _build_status(site, configured=False)
        return AutofillResult(
            status=status,
            decision=decide_takeover(status),
        )

    fields = info.fields
    needs_otp = any(_is_otp_field(f) for f in fields)

    username_field = _match_username_field(fields)
    password_field = _match_password_field(fields)

    used_selectors: set[str] = set()
    if username_field:
        used_selectors.add(username_field.selector)
    if password_field:
        used_selectors.add(password_field.selector)

    errors: list[str] = []

    # 主账号（两步验证等纯 otp 页无 user/pass 字段：不报错，只引导 otp）
    username = str(cred.get("username") or "")
    username_filled = False
    if username_field and username:
        err = await _fill_if_empty(page, username_field, username)
        if err:
            errors.append(f"username: {err}")
        else:
            username_filled = True
    elif username_field is None and not needs_otp:
        errors.append("no username field")

    # 密码
    password = str(cred.get("password") or "")
    password_filled = False
    if password_field and password:
        err = await _fill_if_empty(page, password_field, password)
        if err:
            errors.append(f"password: {err}")
        else:
            password_filled = True
    elif password_field is None and not needs_otp:
        errors.append("no password field")

    # 附加登录信息（可选项；未配置 extra 槽位则跳过）
    extra = cred.get("extra")
    extra_required = False
    extra_filled = False
    if isinstance(extra, dict) and extra.get("field_label"):
        extra_field, extra_err = _match_extra_field(fields, used_selectors, extra)
        if extra_field is not None:
            extra_required = True
            err = await _fill_if_empty(page, extra_field, str(extra.get("value") or ""))
            if err:
                errors.append(f"extra: {err}")
            else:
                extra_filled = True
        elif extra_err:
            errors.append(extra_err)

    fill_error = "; ".join(errors)
    fill_ok = not fill_error

    manual_otp_guided = bool(
        fill_ok
        and needs_otp
        and (username_filled or not username_field)
        and (password_filled or not password_field)
    )
    # 长凭证填完但还有填错（extra 匹配失败等）→ 不标 otp 引导，整体走填失败人工
    if errors and needs_otp:
        manual_otp_guided = False

    status = _build_status(
        site,
        configured=True,
        username_filled=username_filled,
        password_filled=password_filled,
        extra_required=extra_required,
        extra_filled=extra_filled,
        needs_otp=needs_otp,
        manual_otp_guided=manual_otp_guided,
        fill_ok=fill_ok,
        fill_error=fill_error,
    )
    return AutofillResult(status=status, decision=decide_takeover(status))


async def try_autofill(
    page: Any,
    info: LoginFormInfo,
    workspace_id: str | None,
) -> AutofillResult:
    """hook 入口：站点识别 + 读系统凭证 + 自动填写（未配置则只给状态）。

    workspace_id 为空（无活动工作区/测试）时不读 store，按未配置处理。
    """
    site = netloc_of(info.url)
    cred = get_site_credential(workspace_id, site) if workspace_id else None
    result = await autofill_login_form(page, info, cred)
    logger.info(
        "autofill done site=%s configured=%s fill_ok=%s needs_otp=%s manual_otp=%s error=%s",
        result.status.site,
        result.status.configured,
        result.status.fill_ok,
        result.status.needs_otp,
        result.status.manual_otp_guided,
        result.status.fill_error or "-",
    )
    return result
