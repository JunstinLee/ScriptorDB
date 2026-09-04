from __future__ import annotations

import json
from datetime import datetime, timezone

import keyring

from core.logging_setup import get_logger

logger = get_logger("credential_store")

CREDENTIAL_VERSION = 1
CREDENTIAL_SERVICE_SUFFIX = ":site_credential"


class CredentialStorageError(Exception):
    """站点凭证的 keyring 读写失败（非业务校验）。"""


class CredentialCorruptedError(CredentialStorageError):
    """keyring 内已有载荷损坏（非法 JSON / 版本不支持）。"""


def _service(workspace_id: str) -> str:
    # workspace_id 必填 str，不接受 None：config/secrets.py 的 _service(None)
    # 会回退共享 LEGACY_SERVICE，把站点明文凭证写进跨工作区共享的 legacy service。
    return f"scriptordb:{workspace_id}{CREDENTIAL_SERVICE_SUFFIX}"


def _get_password(service: str, site: str) -> str | None:
    try:
        return keyring.get_password(service, site)
    except Exception as e:
        raise CredentialStorageError(
            f"Keyring read failed for site credential '{site}': {e}"
        ) from e


def _safe_delete(service: str, site: str) -> None:
    try:
        keyring.delete_password(service, site)
    except Exception:
        pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload(spec: dict) -> dict:
    """组装持久化载荷：固定 version/site + 透传业务字段 + 时间戳。"""
    payload = {
        "version": CREDENTIAL_VERSION,
        "site": spec.get("site", ""),
        "username": spec.get("username", ""),
        "password": spec.get("password", ""),
    }
    extra = spec.get("extra")
    if isinstance(extra, dict) and extra.get("field_label"):
        payload["extra"] = {
            "field_label": extra.get("field_label", ""),
            "value": extra.get("value", ""),
            "match_hints": extra.get("match_hints") or None,
        }
    payload["updated_at"] = _utc_now_iso()
    return payload


def _parse(value: str, site: str) -> dict:
    try:
        obj = json.loads(value)
    except json.JSONDecodeError as e:
        raise CredentialCorruptedError(
            f"Site credential '{site}' is not valid JSON"
        ) from e
    if not isinstance(obj, dict):
        raise CredentialCorruptedError(
            f"Site credential '{site}' is not a JSON object"
        )
    if obj.get("version") != CREDENTIAL_VERSION:
        raise CredentialCorruptedError(
            f"Site credential '{site}' has an unsupported version"
        )
    return obj


def save_site_credential(workspace_id: str, spec: dict) -> None:
    """写入（或幂等覆盖）一个站点的凭证载荷。

    spec 为载荷 dict（键同持久化 JSON：site/username/password/extra）；
    序列化、版本、时间戳在此层做。明文写入后立即释放局部引用。
    """
    site = spec.get("site") or ""
    payload = _payload(spec)
    service = _service(workspace_id)
    try:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        keyring.set_password(service, site, raw)
    except Exception as e:
        raise CredentialStorageError(
            f"Failed to save site credential '{site}': {e}"
        ) from e
    finally:
        del payload
    logger.debug("credential saved site=%s service=%s", site, service)


def get_site_credential(workspace_id: str, site: str) -> dict | None:
    """读取站点凭证载荷 dict；不存在返回 None。"""
    service = _service(workspace_id)
    value = _get_password(service, site)
    if value is None:
        return None
    try:
        return _parse(value, site)
    except CredentialCorruptedError:
        logger.warning(
            "credential_store: corrupted payload ignored site=%s", site
        )
        return None


def has_site_credential(workspace_id: str, site: str) -> bool:
    try:
        return get_site_credential(workspace_id, site) is not None
    except CredentialStorageError:
        return False


def delete_site_credential(workspace_id: str, site: str) -> None:
    """幂等删除：不存在也成功。仅删当前 workspace 的该 site 条目。"""
    _safe_delete(_service(workspace_id), site)
