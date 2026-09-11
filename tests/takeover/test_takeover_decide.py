"""接管决策（decide_takeover）：由登录流程状态推导 pause / reset。"""

from __future__ import annotations

from typing import Any

from browser.autofill import decide_takeover
from schemas.login_flow import LoginFlowStatus


class TestDecideTakeover:
    def _st(self, **kw) -> LoginFlowStatus:
        base: dict[str, Any] = dict(
            site="example.com",
            login_form_detected=True,
            configured=True,
            username_filled=False,
            password_filled=False,
            extra_required=False,
            extra_filled=False,
            needs_otp=False,
            manual_otp_guided=False,
            fill_ok=False,
            fill_error="",
        )
        base.update(kw)
        return LoginFlowStatus(**base)

    def test_fill_ok_no_otp_resets(self):
        d = decide_takeover(self._st(fill_ok=True))
        assert d.kind == "reset"

    def test_manual_otp_pause_with_mfa(self):
        d = decide_takeover(self._st(fill_ok=True, needs_otp=True, manual_otp_guided=True))
        assert d.kind == "pause"
        assert d.override_reason is True
        assert d.trigger == "mfa"

    def test_configured_fill_error_overrides(self):
        d = decide_takeover(self._st(fill_error="no password field"))
        assert d.kind == "pause"
        assert d.override_reason is True
        assert d.trigger == "autofill_error"

    def test_unconfigured_pause_default_copy(self):
        d = decide_takeover(
            LoginFlowStatus(
                site="example.com", login_form_detected=True, configured=False,
                username_filled=False, password_filled=False, extra_required=False,
                extra_filled=False, needs_otp=False, manual_otp_guided=False,
                fill_ok=False,
            )
        )
        assert d.kind == "pause"
        assert d.override_reason is False
