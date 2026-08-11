from __future__ import annotations

"""Provider model listing/resolution cluster.

- `resolver.py` — model resolution (`resolve_model`, `fuzzy_match_model`, ...)
- `canonical.py` — canonical model registry, loaded from `recommended_models.json`
- `client.py` — provider model-list fetching over HTTP
- `cache.py` — per-provider model-list cache (1h TTL)
"""

from config.models.canonical import (
    CANONICAL_REGISTRY,
    CanonicalModel,
    get_canonical_by_slug,
    get_canonical_for_provider,
    get_canonical_for_provider_model,
)
from config.models.client import filter_chat_models, list_available_models
from config.models.resolver import (
    fuzzy_match_model,
    get_recommended_models,
    list_canonical_models,
    resolve_canonical_slug,
    resolve_model,
)

__all__ = [
    "CANONICAL_REGISTRY",
    "CanonicalModel",
    "filter_chat_models",
    "fuzzy_match_model",
    "get_canonical_by_slug",
    "get_canonical_for_provider",
    "get_canonical_for_provider_model",
    "get_recommended_models",
    "list_available_models",
    "list_canonical_models",
    "resolve_canonical_slug",
    "resolve_model",
]
