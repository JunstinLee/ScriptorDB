from __future__ import annotations

from config.models import fuzzy_match_model


def resolve_user_model(provider: str, model: str) -> str:
    matched = fuzzy_match_model(provider, model)
    if matched and matched != model and not model.startswith(f"{provider}:"):
        return matched
    return model
