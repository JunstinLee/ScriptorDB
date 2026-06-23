from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.canonical_models import get_canonical_by_slug
from config.models import (
    get_recommended_models,
    list_available_models,
    list_canonical_models,
    resolve_canonical_slug,
)
from server.dependencies import get_config
from server.schemas import (
    CanonicalModelItem,
    CanonicalModelsResponse,
    DefaultModelResponse,
    ModelEntry,
    ModelsResponse,
    ModelsWithCanonicalResponse,
)

router = APIRouter(tags=["models"])


def _resolve_provider(provider: str) -> str:
    config = get_config()
    return provider.strip() or config.llm_provider


@router.get("/api/models", response_model=ModelsResponse)
async def get_models(provider: str = ""):
    p = _resolve_provider(provider)
    try:
        models = list_available_models(p)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ModelsResponse(models=models)


@router.get("/api/models/recommended", response_model=ModelsResponse)
async def get_models_recommended(provider: str = ""):
    p = _resolve_provider(provider)
    try:
        models = get_recommended_models(p)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ModelsResponse(models=models)


@router.get("/api/models/with-canonical", response_model=ModelsWithCanonicalResponse)
async def get_models_with_canonical(provider: str = ""):
    """返回带 Canonical 信息的模型列表。

    每条记录包含：
    - provider_specific_id: provider 实际模型 ID
    - canonical_slug: 推断出的 canonical slug（可为空）
    - display_name: 用户面向的展示名（来自 canonical）
    """
    p = _resolve_provider(provider)
    try:
        ids = list_available_models(p)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    entries: list[ModelEntry] = []
    for mid in ids:
        slug = resolve_canonical_slug(p, mid)
        display_name = None
        if slug:
            c = get_canonical_by_slug(slug)
            if c:
                display_name = c.display_name
        entries.append(
            ModelEntry(
                provider_specific_id=mid,
                canonical_slug=slug,
                display_name=display_name,
            )
        )
    return ModelsWithCanonicalResponse(models=entries)


@router.get("/api/canonical-models", response_model=CanonicalModelsResponse)
async def get_canonical_models(provider: str = ""):
    """返回 Canonical Model Registry 中的模型列表。

    - 不传 provider：返回所有 canonical 模型及其 available_providers
    - 传 provider：仅返回该 provider 有 alias 的模型，附带 provider_specific_id
    """
    p = provider.strip() or None
    items = list_canonical_models(p)
    return CanonicalModelsResponse(
        models=[CanonicalModelItem(**item) for item in items]
    )


@router.get("/api/models/default", response_model=DefaultModelResponse)
async def get_default_model(provider: str = ""):
    p = _resolve_provider(provider)
    config = get_config()
    return DefaultModelResponse(model=config.get_default_model(p))
