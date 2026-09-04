from __future__ import annotations

from config.credential_store import (
    delete_site_credential,
    get_site_credential,
    save_site_credential,
)
from browser.login_state import netloc_of
from core.logging_setup import get_logger
from schemas.login_credential import (
    CredentialStatusResponse,
    LoginCredentialSpec,
    SiteStatusRequest,
)

logger = get_logger("login_credential_service")


def _normalize_site(value: str) -> str:
    """归一站点标识：完整 URL 用 netloc_of；裸 host 套用同款去 userinfo/端口/小写。

    站点标识一律与登录表单 URL 的 netloc 对齐（去端口/小写/userinfo，不去 www 子域）。
    """
    v = value.strip()
    if not v:
        return ""
    if "://" in v:
        return netloc_of(v)
    netloc = v.split("@")[-1]
    if ":" in netloc:
        netloc = netloc.rsplit(":", 1)[0]
    return netloc.lower()


def _resolve_site(spec: LoginCredentialSpec) -> str:
    """站点识别：优先 site（归一），校验与 url 归一后一致；site 缺失时用 url 推导。"""
    site_value = spec.site.strip() if spec.site else ""
    url_value = spec.url.strip() if spec.url else ""

    site = _normalize_site(site_value) if site_value else ""
    if url_value:
        url_site = _normalize_site(url_value)
        if site and url_site and site != url_site:
            raise ValueError(
                f"site '{site}' does not match url site '{url_site}'"
            )
        if not site:
            site = url_site
    if not site:
        raise ValueError("site or url is required")
    return site


def _validate_spec(spec: LoginCredentialSpec) -> dict | None:
    """空值校验 + extra 归一；返回待持久化的 extra dict（无则 None）。

    - username/password 空 → ValueError
    - extra field_label 为空 → 忽略整个 extra 槽位（等价 extra=None）
    - extra field_label 非空但 value 空 → ValueError
    """
    if not spec.username or not spec.username.strip():
        raise ValueError("username cannot be empty")
    if not spec.password or not spec.password.strip():
        raise ValueError("password cannot be empty")
    extra = spec.extra
    if extra is None:
        return None
    if not extra.field_label or not extra.field_label.strip():
        # 附加信息可选项：字段名与值都不填不发 extra；字段名空 → 忽略整个槽位
        return None
    if not extra.value or not extra.value.strip():
        raise ValueError("extra value cannot be empty when field_label is set")
    return {
        "field_label": extra.field_label.strip(),
        "value": extra.value,
        "match_hints": extra.match_hints.model_dump() if extra.match_hints else None,
    }


def site_status(workspace_id: str, req: SiteStatusRequest) -> CredentialStatusResponse:
    """站点状态查询：200 恒返（configured=false 也是 200）。"""
    site = _normalize_site(req.url)
    cred = get_site_credential(workspace_id, site) if site else None
    if cred is None:
        return CredentialStatusResponse(site=site, configured=False, site_label=site)
    extra = cred.get("extra")
    label = None
    if isinstance(extra, dict):
        label = extra.get("field_label") or None
    return CredentialStatusResponse(
        site=site,
        configured=True,
        extra_field_label=label,
        site_label=site,
    )


def save(workspace_id: str, spec: LoginCredentialSpec) -> CredentialStatusResponse:
    """保存（幂等覆盖）站点凭证；返回非敏感状态。"""
    extra = _validate_spec(spec)
    site = _resolve_site(spec)

    store_spec: dict = {
        "site": site,
        "username": spec.username,
        "password": spec.password,
    }
    if extra is not None:
        store_spec["extra"] = extra
    save_site_credential(workspace_id, store_spec)

    logger.warning(
        "credential_store: keyring 后端可能为明文回退（无 Secret Service/桌面会话）site=%s",
        site,
    )
    return CredentialStatusResponse(
        site=site,
        configured=True,
        extra_field_label=extra["field_label"] if extra else None,
        site_label=site,
    )


def delete(workspace_id: str, site: str) -> None:
    """幂等删除：不存在也成功（无 404）。"""
    delete_site_credential(workspace_id, site)
