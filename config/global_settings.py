from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from config.workspace_paths import GLOBAL_CONFIG_DIR, GLOBAL_SETTINGS_FILE

if TYPE_CHECKING:
    from config.workspace_settings import WorkspaceSettings


@dataclass
class GlobalSettings:
    llm_provider: str = ""
    llm_model: str | None = None
    default_models: dict[str, str] = field(default_factory=dict)


def load_global_settings() -> GlobalSettings:
    if not GLOBAL_SETTINGS_FILE.exists():
        return GlobalSettings()
    try:
        payload = json.loads(GLOBAL_SETTINGS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return GlobalSettings()
    if not isinstance(payload, dict):
        return GlobalSettings()
    return GlobalSettings(
        llm_provider=str(payload.get("llm_provider") or ""),
        llm_model=payload.get("llm_model"),
        default_models=dict(payload.get("default_models") or {}),
    )


def save_global_settings(gs: GlobalSettings) -> None:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "llm_provider": gs.llm_provider,
        "llm_model": gs.llm_model,
        "default_models": gs.default_models,
    }
    try:
        GLOBAL_SETTINGS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except OSError:
        pass


def apply_global_defaults(ws_settings: WorkspaceSettings) -> None:
    # TODO: 当 UI 支持"单个工作区覆盖全局默认"时，改为检查 ws_settings.use_global_defaults
    # if not ws_settings.use_global_defaults:
    #     return
    global_settings = load_global_settings()
    ws_settings.llm_provider = global_settings.llm_provider
    ws_settings.default_models = dict(global_settings.default_models)
    ws_settings.llm_model = (
        global_settings.default_models.get(global_settings.llm_provider)
        or global_settings.llm_model
    )
