from __future__ import annotations

import json
import time
from pathlib import Path

CACHE_TTL = 3600


def _cache_path(provider: str) -> Path:
    from platformdirs import user_cache_dir

    old_path = Path.home() / ".cache" / "scriptordb"
    if old_path.exists():
        cache_dir = old_path
    else:
        cache_dir = Path(user_cache_dir("scriptordb", ensure_exists=True))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"models_{provider}.json"


def load_cache(provider: str) -> list[str] | None:
    path = _cache_path(provider)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - payload.get("ts", 0) > CACHE_TTL:
        return None
    models = payload.get("models")
    return models if isinstance(models, list) else None


def save_cache(provider: str, models: list[str]) -> None:
    path = _cache_path(provider)
    try:
        path.write_text(json.dumps({"ts": time.time(), "models": models}))
    except OSError:
        pass
