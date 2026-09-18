from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from config.secrets import SUPPORTED_PROVIDERS, get_api_key
from schemas.settings import ApiKeyStatus

KeyProbeStatus = Literal["valid", "invalid", "unknown"]

STATUS_CACHE_TTL_SECONDS = 60

_status_cache: dict[str, tuple[ApiKeyStatus, float]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def probe_key(provider_cfg: Any, api_key: str) -> tuple[KeyProbeStatus, str | None]:
    """Probe an API key and classify the outcome.

    A rejected credential (401/403) means the key is invalid. Network,
    timeout and server-side failures cannot tell us anything about the key,
    so they are reported as ``unknown`` instead of a false "invalid".
    """
    url = f"{provider_cfg.base_url.rstrip('/')}{provider_cfg.list_models_path}"
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code in (401, 403):
            return "invalid", f"API key rejected (HTTP {status_code})"
        return "unknown", f"HTTP {status_code}"
    except Exception as e:
        return "unknown", str(e)
    return "valid", None


def test_key(provider_cfg: Any, api_key: str) -> tuple[bool, str | None]:
    status, error = probe_key(provider_cfg, api_key)
    return status == "valid", error


def check_api_key_status(
    provider: str,
    workspace_id: str | None,
    *,
    force: bool = False,
) -> ApiKeyStatus:
    """Actively determine whether the provider's stored key is usable.

    ``missing``      no key stored for this provider
    ``no_workspace`` no workspace selected, so there is nothing to key against
    ``valid``        the provider accepted the key
    ``invalid``      the provider rejected the key (401/403)
    ``unknown``      the provider could not be reached (network/timeout/5xx)

    Results are cached for ``STATUS_CACHE_TTL_SECONDS``; pass ``force=True``
    to bypass the cache and re-probe immediately.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    if not workspace_id:
        return ApiKeyStatus(
            provider=provider, status="no_workspace", checked_at=_now_iso()
        )

    cache_key = f"{workspace_id}:{provider}"
    if not force:
        cached = _status_cache.get(cache_key)
        if cached is not None and time.monotonic() - cached[1] < STATUS_CACHE_TTL_SECONDS:
            return cached[0]

    try:
        api_key = get_api_key(provider, workspace_id)
    except Exception as e:
        return ApiKeyStatus(
            provider=provider, status="unknown", error=str(e), checked_at=_now_iso()
        )

    if not api_key:
        result = ApiKeyStatus(provider=provider, status="missing", checked_at=_now_iso())
    else:
        probe_status, error = probe_key(SUPPORTED_PROVIDERS[provider], api_key)
        result = ApiKeyStatus(
            provider=provider, status=probe_status, error=error, checked_at=_now_iso()
        )

    _status_cache[cache_key] = (result, time.monotonic())
    return result


def clear_status_cache() -> None:
    """Drop cached probe results (call after a key is saved or removed)."""
    _status_cache.clear()
