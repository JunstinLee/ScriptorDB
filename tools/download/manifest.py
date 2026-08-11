from __future__ import annotations

import json
from pathlib import Path

from schemas.download_models import DownloadManifestEntry

MANIFEST_FILENAME = "downloads_manifest.json"


def manifest_path(outputs_dir: Path) -> Path:
    return outputs_dir / MANIFEST_FILENAME


def load(manifest_path: Path) -> list[DownloadManifestEntry]:
    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(
                DownloadManifestEntry(
                    source_url=str(item.get("source_url", "")),
                    title=str(item.get("title", "")),
                    publish_date=str(item.get("publish_date", "")),
                    filename=str(item.get("filename", "")),
                    size=int(item.get("size", 0)),
                    sha256=str(item.get("sha256", "")),
                    downloaded_at=str(item.get("downloaded_at", "")),
                )
            )
        except (TypeError, ValueError):
            continue
    return entries


def append(entry: DownloadManifestEntry, manifest_path: Path) -> None:
    entries = load(manifest_path)
    entries.append(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in entries]
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
