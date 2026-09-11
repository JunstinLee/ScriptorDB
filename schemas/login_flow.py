from __future__ import annotations

from pydantic import BaseModel


class LoginFlowStatus(BaseModel):
    """登录流程状态（非敏感：不含任何凭证明文/验证码值）。

    由 autofill 服务构造、经 SSE `login_flow_status` 事件推前端；
    前端只用布尔与错误文案做状态展示，凭证明文永不进入事件。
    """

    site: str
    login_form_detected: bool
    configured: bool  # 该站点是否有系统凭证
    username_filled: bool
    password_filled: bool
    extra_required: bool  # 凭证含 extra 且页面有候选字段
    extra_filled: bool
    needs_otp: bool  # 存在必填 otp 字段（留待用户手动）
    manual_otp_guided: bool  # 长凭证已填、已引导用户到 Chrome 手动输验证码
    fill_ok: bool
    fill_error: str = ""
