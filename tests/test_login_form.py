from __future__ import annotations

from browser.login_form import (
    ROLE_OTP,
    ROLE_PASSWORD,
    ROLE_UNKNOWN,
    ROLE_USERNAME,
    _classify_role,
    _is_submit,
    extract_login_form,
    format_login_form_message,
)


class _FakePage:
    """最小 Page 接口：登录信号与字段提取 JS 各自返回预置结果。"""

    def __init__(self, url: str, controls: list[dict] | None = None,
                 title: str = "Dashboard", has_password: bool = False):
        self.url = url
        self._controls = controls or []
        self._title = title
        self._has_password = has_password
        self.context = None  # LoginPage 协议要求；extract 不使用

    async def title(self) -> str:
        return self._title

    async def evaluate(self, expression: str, arg=None):
        # login_state._PASSWORD_INPUT_JS（无引号的 type=password 选择器）
        if "input[type=password]" in expression:
            return self._has_password
        return self._controls


def _login_page(controls: list[dict] | None = None) -> _FakePage:
    return _FakePage("https://example.com/login", controls, title="Sign in")


class TestClassifyRole:
    def test_password_by_type(self):
        assert _classify_role({"type": "password"}) == ROLE_PASSWORD

    def test_username_by_autocomplete(self):
        assert _classify_role({"type": "text", "autocomplete": "username"}) == ROLE_USERNAME
        assert _classify_role({"type": "email", "autocomplete": "email"}) == ROLE_USERNAME

    def test_otp_by_autocomplete(self):
        assert _classify_role({"type": "text", "autocomplete": "one-time-code"}) == ROLE_OTP

    def test_otp_by_name(self):
        assert _classify_role({"name": "otp_code"}) == ROLE_OTP
        assert _classify_role({"placeholder": "验证码"}) == ROLE_OTP

    def test_username_by_name(self):
        assert _classify_role({"name": "email"}) == ROLE_USERNAME
        assert _classify_role({"id": "user_account"}) == ROLE_USERNAME

    def test_password_by_name(self):
        assert _classify_role({"name": "passwd"}) == ROLE_PASSWORD

    def test_unknown_field(self):
        assert _classify_role({"name": "csrf_token"}) == ROLE_UNKNOWN


class TestIsSubmit:
    def test_input_submit(self):
        assert _is_submit({"tag": "input", "type": "submit"}) is True

    def test_button_submit(self):
        assert _is_submit({"tag": "button", "type": "submit"}) is True

    def test_button_text_keyword(self):
        assert _is_submit({"tag": "button", "type": "button", "text": "Sign in"}) is True
        assert _is_submit({"tag": "button", "type": "button", "text": "登录"}) is True

    def test_non_submit_input(self):
        assert _is_submit({"tag": "input", "type": "text"}) is False


class TestExtractLoginForm:
    async def test_login_page_fields(self):
        page = _login_page([
            {"tag": "input", "type": "text", "name": "email", "id": "email",
             "placeholder": "Email", "label": "", "text": "",
             "autocomplete": "email", "required": True, "selector": "#email",
             "visible": True, "in_form": True},
            {"tag": "input", "type": "password", "name": "password", "id": "",
             "placeholder": "", "label": "Password", "text": "",
             "autocomplete": "current-password", "required": True,
             "selector": 'input[type="password"]', "visible": True, "in_form": True},
            {"tag": "button", "type": "submit", "name": "", "id": "", "label": "",
             "text": "Sign in", "selector": "button[type=\"submit\"]",
             "visible": True, "in_form": True},
        ])
        info = await extract_login_form(page)
        assert info is not None
        assert info.is_login_page is True
        assert [f.role for f in info.fields] == [ROLE_USERNAME, ROLE_PASSWORD]
        assert info.fields[0].selector == "#email"
        assert info.fields[0].required is True
        assert info.fields[1].label == "Password"
        assert info.submit is not None
        assert info.submit.selector == 'button[type="submit"]'

    async def test_non_login_page_returns_none(self):
        page = _FakePage("https://example.com/dashboard", title="Dashboard")
        assert await extract_login_form(page) is None

    async def test_hidden_controls_filtered(self):
        page = _login_page([
            {"tag": "input", "type": "text", "name": "user", "visible": True,
             "selector": '[name="user"]'},
            {"tag": "input", "type": "hidden", "name": "csrf", "visible": False,
             "selector": '[name="csrf"]'},
        ])
        info = await extract_login_form(page)
        assert info is not None
        assert len(info.fields) == 1
        assert info.fields[0].name == "user"

    async def test_formless_page_fallback(self):
        page = _FakePage(
            "https://example.com/login",
            [{"tag": "input", "type": "text", "name": "login", "visible": True,
              "selector": '[name="login"]', "in_form": False}],
            title="Sign in",
        )
        info = await extract_login_form(page)
        assert info is not None
        assert info.fields[0].role == ROLE_USERNAME
        assert info.fields[0].in_form is False


class TestSignatureAndFormat:
    async def test_signature_equal_for_same_form(self):
        controls = [
            {"tag": "input", "type": "text", "name": "email", "visible": True,
             "selector": "#email"},
            {"tag": "input", "type": "password", "name": "password", "visible": True,
             "selector": "#password"},
        ]
        a = await extract_login_form(_login_page(controls))
        b = await extract_login_form(_login_page(list(controls)))
        assert a is not None and b is not None
        assert a.signature() == b.signature()

    async def test_signature_differs_when_roles_change(self):
        page = _login_page([
            {"tag": "input", "type": "text", "name": "email", "visible": True,
             "selector": "#email"},
        ])
        info = await extract_login_form(page)
        assert info is not None
        altered = await extract_login_form(_login_page([
            {"tag": "input", "type": "password", "name": "email", "visible": True,
             "selector": "#email"},
        ]))
        assert altered is not None
        assert info.signature() != altered.signature()

    async def test_format_message(self):
        page = _login_page([
            {"tag": "input", "type": "text", "name": "email", "label": "邮箱",
             "required": True, "visible": True, "selector": "#email"},
            {"tag": "input", "type": "password", "name": "password", "visible": True,
             "selector": "#password"},
            {"tag": "button", "type": "submit", "text": "Sign in", "visible": True,
             "selector": "button[type=\"submit\"]"},
        ])
        info = await extract_login_form(page)
        assert info is not None
        msg = format_login_form_message(info)
        assert "#email" in msg
        assert "[必填]" in msg
        assert "提交按钮" in msg
        assert "#password" in msg
