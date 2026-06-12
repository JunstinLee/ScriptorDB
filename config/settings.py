from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.secrets import get_api_key
from config.models import resolve_model

_CONFIG_DIR = Path.home() / ".config" / "scriptordb"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_config(config: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    except OSError:
        pass


@dataclass
class Settings:
    llm_provider: str = "openai"
    db_url: str = "sqlite:///scriptordb.sqlite"
    llm_model: Optional[str] = field(default=None)
    default_models: dict[str, str] = field(default_factory=dict)
    auto_restore_sessions: bool = True

    def __post_init__(self) -> None:
        config = _load_config()
        if "llm_provider" in config:
            self.llm_provider = config["llm_provider"]
        if "default_models" in config and isinstance(config["default_models"], dict):
            self.default_models = config["default_models"]
        if "auto_restore_sessions" in config and isinstance(
            config["auto_restore_sessions"], bool
        ):
            self.auto_restore_sessions = config["auto_restore_sessions"]
        if not self.llm_model:
            self.llm_model = self.default_models.get(self.llm_provider)

    @property
    def llm_api_key(self) -> str:
        key = get_api_key(self.llm_provider)
        if key is None:
            raise RuntimeError(
                f"No API key found for {self.llm_provider}. Run 'python main.py setup' first."
            )
        return key

    @property
    def resolved_model(self) -> str:
        return resolve_model(self.llm_provider, self.llm_model)

    def set_default_model(self, provider: str, model: str) -> None:
        self.default_models[provider] = model
        config = _load_config()
        config["default_models"] = self.default_models
        if self.llm_provider == provider:
            self.llm_model = model
            config["llm_provider"] = self.llm_provider
        config["auto_restore_sessions"] = self.auto_restore_sessions
        _save_config(config)

    def get_default_model(self, provider: str) -> str | None:
        return self.default_models.get(provider)

    def set_provider(self, provider: str) -> None:
        self.llm_provider = provider
        if provider in self.default_models:
            self.llm_model = self.default_models[provider]
        self._persist()

    def set_auto_restore_sessions(self, value: bool) -> None:
        self.auto_restore_sessions = value
        self._persist()

    def _persist(self) -> None:
        config = _load_config()
        config["llm_provider"] = self.llm_provider
        config["default_models"] = self.default_models
        config["auto_restore_sessions"] = self.auto_restore_sessions
        _save_config(config)


settings = Settings()
