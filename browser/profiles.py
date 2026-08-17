from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from browser.login_state import LoginState, detect_login_state, netloc_of
from config.secrets import delete_browser_profile, get_browser_profile, save_browser_profile
from core.logging_setup import get_logger

logger = get_logger("browser.profiles")

if TYPE_CHECKING:
    from browser.manager import BrowserManager


@dataclass
class ProfileMeta:
    name: str
    domain: str
    cookie_count: int
    created_at: str
    updated_at: str


def _profiles_dir(workspace_path: Path) -> Path:
    return workspace_path / ".scriptordb" / "browser_profiles"


def _index_path(workspace_path: Path) -> Path:
    return _profiles_dir(workspace_path) / "_index.json"


def _meta_to_dict(meta: ProfileMeta) -> dict:
    return {
        "domain": meta.domain,
        "cookie_count": meta.cookie_count,
        "created_at": meta.created_at,
        "updated_at": meta.updated_at,
    }


def _load_index(workspace_path: Path) -> dict:
    path = _index_path(workspace_path)
    if not path.exists():
        return {"version": 1, "profiles": {}}
    with open(path, "r") as f:
        return json.load(f)


def _save_index(workspace_path: Path, index: dict) -> None:
    _profiles_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    with open(_index_path(workspace_path), "w") as f:
        json.dump(index, f, indent=2, default=str)


class BrowserNotLaunchedError(Exception):
    pass


async def save_current_profile(
    manager: BrowserManager, name: str, workspace_id: str, workspace_path: Path
) -> ProfileMeta:
    page = manager.page()
    if not page:
        raise BrowserNotLaunchedError()

    storage_state = await page.context.storage_state()
    save_browser_profile(workspace_id, name, storage_state)  # type: ignore[arg-type]

    cookies = storage_state.get("cookies", [])
    current_url = page.url
    domain = urlparse(current_url).netloc
    now = datetime.now(timezone.utc).isoformat()

    meta = ProfileMeta(
        name=name, domain=domain,
        cookie_count=len(cookies),
        created_at=now, updated_at=now,
    )

    index = _load_index(workspace_path)
    if name in index["profiles"]:
        meta.created_at = index["profiles"][name]["created_at"]
    index["profiles"][name] = _meta_to_dict(meta)
    _save_index(workspace_path, index)

    return meta


def list_profiles(workspace_path: Path) -> list[dict]:
    index = _load_index(workspace_path)
    profiles = []
    for name, data in index.get("profiles", {}).items():
        profiles.append({"name": name, **data})
    return profiles


def delete_profile(name: str, workspace_id: str, workspace_path: Path) -> bool:
    delete_browser_profile(workspace_id, name)

    index = _load_index(workspace_path)
    if name not in index["profiles"]:
        return False
    del index["profiles"][name]
    _save_index(workspace_path, index)
    return True


async def load_profile(manager: BrowserManager, name: str, workspace_id: str) -> bool:
    storage_state = get_browser_profile(workspace_id, name)
    if storage_state is None:
        return False

    page = manager.page()
    if not page:
        raise BrowserNotLaunchedError()

    if storage_state.get("cookies"):
        await page.context.add_cookies(storage_state["cookies"])

    original_url = page.url
    for origin_data in storage_state.get("origins", []):
        origin = origin_data.get("origin")
        local_storage_items = origin_data.get("localStorage", [])
        if not origin or not local_storage_items:
            continue
        await page.goto(origin, wait_until="domcontentloaded")
        for item in local_storage_items:
            await page.evaluate(
                f"localStorage.setItem({json.dumps(item['name'])}, {json.dumps(item['value'])})"
            )
    if original_url:
        await page.goto(original_url, wait_until="domcontentloaded")

    expected = [c["name"] for c in storage_state.get("cookies", []) if c.get("name")]
    state = await detect_login_state(page, expected_cookie_names=expected or None)
    logger.info(
        "profile '%s' restored: login_state=%s reason=%s domain=%s",
        name, state.status, state.reason, state.domain,
    )
    return True


async def validate_profile(manager: BrowserManager, name: str, workspace_id: str) -> LoginState:
    """校验已保存 profile 的登录态在当前浏览器会话中是否仍然有效。

    依据：profile 保存时的 cookie 名集合。只要关键会话 cookie 仍在，视为有效。
    不导航、不改动页面状态，可在任意页面调用。
    """
    storage_state = get_browser_profile(workspace_id, name)
    if storage_state is None:
        return LoginState(status="unknown", reason=f"profile '{name}' 不存在")

    page = manager.page()
    if not page:
        raise BrowserNotLaunchedError()

    cookies = storage_state.get("cookies", [])
    expected = [c["name"] for c in cookies if c.get("name")]

    # 当前页面无有效域名时，用 profile cookie 中出现最多的域名兜底
    domain = None
    if not netloc_of(page.url):
        domains = [str(c.get("domain", "")).lstrip(".") for c in cookies if c.get("domain")]
        if domains:
            from collections import Counter

            domain = Counter(domains).most_common(1)[0][0]

    return await detect_login_state(
        page,
        domain=domain,
        expected_cookie_names=expected or None,
    )


def profile_exists(name: str, workspace_id: str, workspace_path: Path) -> bool:
    index = _load_index(workspace_path)
    return name in index.get("profiles", {})
