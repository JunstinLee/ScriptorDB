from __future__ import annotations

from typing import Any

import httpx


def test_key(provider_cfg: Any, api_key: str) -> tuple[bool, str | None]:
    url = f"{provider_cfg.base_url.rstrip('/')}{provider_cfg.list_models_path}"
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return False, str(e)
    return True, None
