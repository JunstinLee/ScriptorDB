from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DownloadResult:
    url: str
    success: bool = False
    error: str | None = None
    filename: str | None = None
    path: str | None = None
    size: int | None = None
    sha256: str | None = None
    content_type: str | None = None
    downloaded_at: str = field(default_factory=_utc_now_iso)


@dataclass
class DownloadManifestEntry:
    source_url: str
    filename: str
    size: int
    sha256: str
    title: str = ""
    publish_date: str = ""
    downloaded_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "title": self.title,
            "publish_date": self.publish_date,
            "filename": self.filename,
            "size": self.size,
            "sha256": self.sha256,
            "downloaded_at": self.downloaded_at,
        }
