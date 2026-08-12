from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CanonicalModel:
    slug: str
    display_name: str
    aliases: dict[str, str] = field(default_factory=dict)


def _load_registry(path: Path | None = None) -> tuple[CanonicalModel, ...]:
    if path is None:
        path = Path(__file__).parent / "recommended_models.json"

    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read recommended_models.json: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in recommended_models.json: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("recommended_models.json must contain a JSON array")

    slugs: set[str] = set()
    models: list[CanonicalModel] = []

    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Entry {idx} in recommended_models.json must be an object"
            )

        slug = entry.get("slug")
        display_name = entry.get("display_name")
        aliases = entry.get("aliases")

        if not isinstance(slug, str) or not slug:
            raise ValueError(
                f"Entry {idx} in recommended_models.json missing or invalid 'slug'"
            )

        if slug in slugs:
            raise ValueError(
                f"Duplicate slug '{slug}' in recommended_models.json"
            )
        slugs.add(slug)

        if not isinstance(display_name, str) or not display_name:
            raise ValueError(
                f"Entry '{slug}' in recommended_models.json missing or invalid 'display_name'"
            )

        if not isinstance(aliases, dict):
            raise ValueError(
                f"Entry '{slug}' in recommended_models.json missing or invalid 'aliases'"
            )

        for provider, alias in aliases.items():
            if not isinstance(provider, str) or not provider:
                raise ValueError(
                    f"Entry '{slug}' has invalid provider key in aliases"
                )
            if not isinstance(alias, str) or not alias:
                raise ValueError(
                    f"Entry '{slug}' has invalid alias for provider '{provider}'"
                )

        models.append(CanonicalModel(
            slug=slug,
            display_name=display_name,
            aliases=aliases,
        ))

    return tuple(models)


CANONICAL_REGISTRY: tuple[CanonicalModel, ...] = _load_registry()


def get_canonical_by_slug(slug: str) -> CanonicalModel | None:
    for m in CANONICAL_REGISTRY:
        if m.slug == slug:
            return m
    return None


def _strip_date_suffix(name: str) -> str:
    import re

    return re.sub(
        r"[-_](?:\d{8}|\d{4}[-_]?\d{2}[-_]?\d{2}|v\d+|\d+)$",
        "",
        name,
    )


def _strip_provider_prefix(name: str) -> str:
    if "/" in name:
        return name.split("/", 1)[1]
    return name


def get_canonical_for_provider_model(provider: str, model_id: str) -> CanonicalModel | None:
    if not model_id:
        return None

    lower = model_id.lower()

    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() == lower:
            return m

    base = _strip_date_suffix(_strip_provider_prefix(model_id)).lower()
    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() == base:
            return m

    for m in CANONICAL_REGISTRY:
        alias = m.aliases.get(provider)
        if alias and alias.lower() in lower:
            return m
        if m.slug.lower() in lower:
            return m

    for m in CANONICAL_REGISTRY:
        for other_provider, other_alias in m.aliases.items():
            if other_alias and other_alias.lower() == lower:
                return m

    return None


def get_canonical_for_provider(provider: str) -> list[CanonicalModel]:
    return [m for m in CANONICAL_REGISTRY if provider in m.aliases]
