from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config.secrets import get_api_key
from config.models import resolve_model


@dataclass
class Settings:
    llm_provider: str = "openai"
    db_url: str = "sqlite:///scriptordb.sqlite"
    llm_model: Optional[str] = field(default=None)

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


settings = Settings()
