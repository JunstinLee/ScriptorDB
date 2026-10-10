"""浏览器下载的落盘与记录。

从 :class:`browser.manager.BrowserManager` 抽出：与浏览器控制无关的文件命名 /
去重 / manifest 追加，以及「最近下载」记录（供工具层轮询确认下载是否发生）。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from core.logging_setup import get_logger

logger = get_logger("browser.downloads")

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    name = _INVALID_FILENAME_CHARS.sub("_", name).strip()
    return name or "download.bin"


def _unique_path(output_dir: Path, filename: str) -> Path:
    stem, dot, suffix = filename.rpartition(".")
    path = output_dir / filename
    counter = 1
    while path.exists():
        if dot:
            path = output_dir / f"{stem} ({counter}){dot}{suffix}"
        else:
            path = output_dir / f"{stem} ({counter})"
        counter += 1
    return path


def _append_manifest(output_dir: Path, entry: dict) -> None:
    manifest_file = output_dir / "downloads_manifest.json"
    entries: list = []
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries = data
        except (OSError, json.JSONDecodeError):
            entries = []
    entries.append(entry)
    manifest_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


class DownloadRecorder:
    """保存浏览器下载并维护最近 20 条下载记录。"""

    def __init__(self) -> None:
        self._dir: Path | None = None
        self._recent: list[dict] = []

    def set_dir(self, path: Path | None) -> None:
        """设置下载文件的保存目录；None 表示不自动保存。"""
        self._dir = Path(path) if path else None

    def recent(self, since: float) -> list[dict]:
        """返回 since（含）之后收到的下载记录。"""
        return [r for r in self._recent if r.get("ts", 0) >= since]

    def _record(self, *, ok: bool, **fields) -> None:
        self._recent.append({"ok": ok, "ts": time.time(), **fields})
        if len(self._recent) > 20:
            self._recent = self._recent[-20:]

    async def handle(self, download) -> None:
        """任意浏览器下载自动保存到设置目录，结果记入最近记录。"""
        if not self._dir:
            logger.warning("download event ignored: downloads dir not configured")
            self._record(ok=False, reason="downloads dir not configured")
            return
        try:
            if failure := await download.failure():
                logger.warning(f"download failed: {failure}")
                self._record(ok=False, reason=f"download failed: {failure}")
                return
            self._dir.mkdir(parents=True, exist_ok=True)
            filename = _sanitize_filename(download.suggested_filename or "download.bin")
            path = _unique_path(self._dir, filename)
            await download.save_as(path)
            size = path.stat().st_size
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            _append_manifest(self._dir, {
                "source_url": download.url if hasattr(download, "url") else "",
                "title": "",
                "publish_date": "",
                "filename": path.name,
                "size": size,
                "sha256": sha256,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"download saved: {path} ({size} bytes)")
            self._record(ok=True, filename=path.name, path=str(path), size=size)
        except Exception as e:
            logger.warning(f"download save failed: {e}")
            self._record(ok=False, reason=f"download save failed: {e}")
