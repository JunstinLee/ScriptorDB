from __future__ import annotations

from pydantic import BaseModel


class ModelsResponse(BaseModel):
    models: list[str]


class DefaultModelResponse(BaseModel):
    model: str | None


class CanonicalModelItem(BaseModel):
    slug: str
    display_name: str
    provider_specific_id: str | None = None
    available_providers: list[str] | None = None


class CanonicalModelsResponse(BaseModel):
    models: list[CanonicalModelItem]


class ModelEntry(BaseModel):
    provider_specific_id: str
    canonical_slug: str | None = None
    display_name: str | None = None


class ModelsWithCanonicalResponse(BaseModel):
    models: list[ModelEntry]
