from __future__ import annotations

from pydantic import BaseModel


class MatchHints(BaseModel):
    """保存时从当前页捕获的第三项字段特征，供后续 autofill 匹配（03）。"""

    name: str = ""
    id: str = ""
    label: str = ""
    placeholder: str = ""


class ExtraCredential(BaseModel):
    """附加登录信息（第三项）。无 extra 时传 None，不传空对象。"""

    field_label: str  # 用户填的字段名，如 "User ID" / "Account ID" / "员工号"
    value: str
    match_hints: MatchHints | None = None


class LoginCredentialSpec(BaseModel):
    """POST /api/credentials 保存请求体。"""

    site: str | None = None  # 站点 netloc；省略时由服务层用 url 推导
    url: str | None = None  # 保存时前端所在页面 URL；site 缺失时服务层用它推导 site
    username: str
    password: str
    extra: ExtraCredential | None = None


class SiteStatusRequest(BaseModel):
    """POST /api/credentials/site-status 请求体。"""

    url: str  # 当前页 URL，服务层 netloc_of 归一为 site


class CredentialStatusResponse(BaseModel):
    """状态响应（非敏感，前端只消费这个）。

    不含 username/password/extra.value；仅含布尔/元数据。
    """

    site: str
    configured: bool
    extra_field_label: str | None = None  # 已保存的附加字段名（不含值），仅用于 UI 提示
    site_label: str = ""  # 展示用，= site 的 netloc（无自定义名）
