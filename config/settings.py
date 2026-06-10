from __future__ import annotations

from dataclasses import dataclass

from config.secrets import SUPPORTED_PROVIDERS, get_api_key


@dataclass
class Settings:
    llm_provider: str = "openai"
    db_url: str = "sqlite:///scriptordb.sqlite"

    @property
    def llm_model(self) -> str:
        return SUPPORTED_PROVIDERS[self.llm_provider]

    @property
    def llm_api_key(self) -> str:
        key = get_api_key(self.llm_provider)
        if key is None:
            raise RuntimeError(
                f"No API key found for {self.llm_provider}. Run 'python main.py setup' first."
            )
        return key


settings = Settings()
