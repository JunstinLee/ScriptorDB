from __future__ import annotations

from config.models import fuzzy_match_model


def resolve_user_model(provider: str, model: str, workspace_id: str | None = None) -> str:
    matched = fuzzy_match_model(provider, model, workspace_id)
    if matched and matched != model and not model.startswith(f"{provider}:"):
        return matched
    return model
