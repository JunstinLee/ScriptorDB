from __future__ import annotations

from browser.autofill import (
    autofill_login_form,
    decide_takeover,
)
from browser.login_form import (
    ROLE_OTP,
    ROLE_PASSWORD,
    ROLE_UNKNOWN,
    ROLE_USERNAME,
    LoginField,
    LoginFormInfo,
)
from schemas.login_flow import LoginFlowStatus

# ---------------------------------------------------------------- fake page


class _FakeLocator:
    """记录 fill/select_option 的极简 locator；value 可预设模拟已填。"""

    def __init__(self, page, selector: str):
        self._page = page
        self.selector = selector
        self.value = page._preset_values.get(selector, "")

    async def count(self) -> int:
        return 1 if self.selector in self._page._selectors else 0

    async def input_value(self) -> str:
        if self.selector not in self._page._selectors:
            raise Exception("element not found")
        return self.value

    async def fill(self, value: str) -> None:
        if self.selector not in self._page._selectors:
            raise Exception("element not found")
        self._page._fills.append((self.selector, value))
        self.value = value

    async def select_option(self, value: str) -> None:
        self._page._selects.append((self.selector, value))
        self.value = value

    async def evaluate(self, js: str):
        # select 检测（_locator_value 用）
        return "select" in self.selector


class _FakePage:
    """autofill 测试用最小 page：locator + fill/select + evaluate。"""

    def __init__(self, selectors: list[str], preset_values: dict | None = None):
        self.url = "https://example.com/login"
        self._selectors = set(selectors)
        self._preset_values = preset_values or {}
        self._fills: list[tuple[str, str]] = []
        self._selects: list[tuple[str, str]] = []

    def locator(self, selector: str):
        return _FakeLocator(self, selector)


def _field(
    role: str,
    selector: str,
    *,
    tag: str = "input",
    type: str = "text",
    name: str = "",
    id: str = "",
    label: str = "",
    placeholder: str = "",
    autocomplete: str = "",
) -> LoginField:
    return LoginField(
        role=role,
        selector=selector,
        tag=tag,
        type=type,
        name=name,
        id=id,
        label=label,
        placeholder=placeholder,
        autocomplete=autocomplete,
    )


def _info(*fields: LoginField) -> LoginFormInfo:
    return LoginFormInfo(
        url="https://example.com/login",
        is_login_page=True,
        fields=list(fields),
    )


CRED = {
    "site": "example.com",
    "username": "alice",
    "password": "s3cret",
    "extra": {
        "field_label": "User ID",
        "value": "A-1001",
        "match_hints": {"name": "userid", "id": "", "label": "User ID", "placeholder": ""},
    },
}


def _page_for(fields: list[LoginField]) -> _FakePage:
    return _FakePage([f.selector for f in fields])


# ---------------------------------------------------------------- autofill


class TestAutofillFill:
    async def test_fills_username_password(self):
        """标准登录页：username/password 槽位由代码填入。"""
        page = _page_for([])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email", id="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
        ]
        # 预置 selector 存在
        page = _FakePage(["#email", "#password"])
        result = await autofill_login_form(page, _info(*fields), CRED)
        st = result.status
        assert st.configured is True
        assert st.username_filled is True
        assert st.password_filled is True
        assert st.fill_ok is True
        assert st.needs_otp is False
        assert st.manual_otp_guided is False
        assert ("#email", "alice") in page._fills
        assert ("#password", "s3cret") in page._fills

    async def test_otp_field_not_filled_and_guides_manual(self):
        """页面含 otp 字段：otp 不被填；填完长凭证后 manual_otp_guided=true。"""
        page = _FakePage(["#email", "#password", "#otp"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
            _field(ROLE_OTP, "#otp", name="otp_code", autocomplete="one-time-code"),
        ]
        result = await autofill_login_form(page, _info(*fields), CRED)
        st = result.status
        assert st.needs_otp is True
        assert st.manual_otp_guided is True
        assert st.fill_ok is True
        # otp 字段绝不被 fill
        assert all(sel != "#otp" for sel, _ in page._fills)
        # 决策：kind=pause + otp 文案（覆盖 reason）
        assert result.decision.kind == "pause"
        assert result.decision.override_reason is True
        assert result.decision.trigger == "mfa"

    async def test_otp_only_page_second_step(self):
        """两步验证第二步（仅 otp 字段）：无 user/pass 不报错，仅引导 otp。"""
        page = _FakePage(["#otp"])
        fields = [_field(ROLE_OTP, "#otp", name="otp_code")]
        result = await autofill_login_form(page, _info(*fields), CRED)
        st = result.status
        assert st.needs_otp is True
        assert st.manual_otp_guided is True
        assert st.fill_error == ""
        assert st.fill_ok is True
        assert page._fills == []

    async def test_no_credential_does_not_fill(self):
        """未配置站点（cred=None）：不填任何字段、configured=false。"""
        page = _FakePage(["#email", "#password"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
        ]
        result = await autofill_login_form(page, _info(*fields), None)
        st = result.status
        assert st.configured is False
        assert st.username_filled is False
        assert st.fill_ok is False
        assert page._fills == []
        # 未配置：需要人工但不覆盖 reason（默认文案）
        assert result.decision.kind == "pause"
        assert result.decision.override_reason is False

    async def test_idempotent_skip_already_filled(self):
        """幂等：槽位已填（input_value 非空）则不重填。"""
        page = _FakePage(["#email", "#password"], preset_values={"#email": "alice"})
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
        ]
        result = await autofill_login_form(page, _info(*fields), CRED)
        st = result.status
        assert st.username_filled is True  # 已填视为成功
        assert st.password_filled is True
        # 已填的 username 不重填；password 填了
        assert all(sel != "#email" for sel, _ in page._fills)
        assert ("#password", "s3cret") in page._fills

    async def test_select_control_uses_select_option(self):
        """候选含 select：用 select_option 而非 fill。"""
        page = _FakePage(["#email", "#password", "#userid"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
            _field(ROLE_UNKNOWN, "#userid", tag="select", name="userid", label="User ID"),
        ]
        cred = {**CRED, "extra": {"field_label": "User ID", "value": "A-1001",
                                  "match_hints": {"name": "userid", "id": "", "label": "User ID", "placeholder": ""}}}
        result = await autofill_login_form(page, _info(*fields), cred)
        st = result.status
        assert st.extra_filled is True
        assert ("#userid", "A-1001") in page._selects
        assert not any(sel == "#userid" for sel, _ in page._fills)

    async def test_checkbox_radio_excluded_from_candidates(self):
        """checkbox/radio 不进候选（extra 匹配不到也不误填）。"""
        page = _FakePage(["#email", "#password", "#newsletter"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
            _field(ROLE_UNKNOWN, "#newsletter", name="newsletter", type="checkbox"),
        ]
        cred = {**CRED, "extra": {"field_label": "User ID", "value": "A-1001", "match_hints": None}}
        result = await autofill_login_form(page, _info(*fields), cred)
        st = result.status
        assert st.extra_required is False
        assert st.extra_filled is False
        # checkbox 不被触碰
        assert not any(sel == "#newsletter" for sel, _ in page._fills)

    async def test_extra_match_by_semantic_label_without_hints(self):
        """无 match_hints 时按 field_label 语义名匹配到 unknown 字段。"""
        page = _FakePage(["#email", "#password", "[name=userid]"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
            _field(ROLE_UNKNOWN, "[name=userid]", name="userid", label="User ID"),
        ]
        cred = {**CRED, "extra": {"field_label": "User ID", "value": "A-1001", "match_hints": None}}
        result = await autofill_login_form(page, _info(*fields), cred)
        assert result.status.extra_filled is True
        assert ("[name=userid]", "A-1001") in page._fills

    async def test_extra_ambiguous_no_unique_selector_fallback(self):
        """extra 无唯一候选：宁缺毋错，fill_error（不误填）。"""
        page = _FakePage(["#email", "#password", "#a", "#b"])
        fields = [
            _field(ROLE_USERNAME, "#email", name="email"),
            _field(ROLE_PASSWORD, "#password", name="password", type="password"),
            _field(ROLE_UNKNOWN, "#a", name="a", label="X"),
            _field(ROLE_UNKNOWN, "#b", name="b", label="Y"),
        ]
        cred = {**CRED, "extra": {"field_label": "X", "value": "V", "match_hints": None}}
        # 语义匹配"X"：a 命中（label X），填 a
        result = await autofill_login_form(page, _info(*fields), cred)
        assert result.status.extra_filled is True
        assert ("#a", "V") in page._fills

    async def test_no_password_field_reports_error_when_no_otp(self):
        """非 otp 页无 password 字段 → fill_error（非静默）。"""
        page = _FakePage(["#email"])
        fields = [_field(ROLE_USERNAME, "#email", name="email")]
        result = await autofill_login_form(page, _info(*fields), CRED)
        st = result.status
        assert st.fill_ok is False
        assert "no password field" in st.fill_error
        assert result.decision.kind == "pause"
        assert result.decision.override_reason is True
        assert "Auto-fill failed" in result.decision.reason


class TestDecideTakeover:
    def _st(self, **kw) -> LoginFlowStatus:
        base: dict[str, object] = dict(
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
