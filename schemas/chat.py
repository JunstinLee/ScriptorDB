from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    provider: str | None = None
    attachments: list[str] = Field(default_factory=list)
    crawl_url: str | None = None
