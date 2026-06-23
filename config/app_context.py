from __future__ import annotations

from dataclasses import dataclass

from config.app_config import AppConfig


@dataclass
class AppContext:
    config: AppConfig
    _agent: object = None
    _agent_signature: tuple[str, str, str | None] | None = None
