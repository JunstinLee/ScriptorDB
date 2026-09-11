from __future__ import annotations

import hashlib
import re
from pathlib import Path

import httpx

from config.workspace_paths import workspace_outputs_dir
from schemas.download_models import DownloadResult
from tools.policy.download_policy import DownloadPolicyError, is_allowed_type, validate_domain
from core.logging_setup import get_logger

logger = get_logger("download_service")

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_MAX_RETRIES = 2
_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
_DEFAULT_USER_AGENT = "ScriptorDB/1.0 (+download tool)"

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class DownloadServiceError(Exception):
    pass


def _ext_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower()


def _ext_of(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot + 1:].lower() if dot != -1 else ""


def _parse_content_disposition_filename(content_disposition: str) -> str:
    for part in content_disposition.split(";"):
        part = part.strip()
        if part.lower().startswith("filename="):
            return part[len("filename="):].strip().strip('"').strip("'")
    return ""


def _sanitize_filename(name: str) -> str:
    name = name.replace("\\", "_").replace("/", "_")
    name = _INVALID_FILENAME_CHARS.sub("_", name)
    name = name.strip(" .")
    return name


def _infer_filename(headers: httpx.Headers, final_url: str, filename_hint: str | None) -> str:
    name = _parse_content_disposition_filename(headers.get("content-disposition", ""))
    if not name:
        name = httpx.URL(final_url).path.split("/")[-1] or ""
    if not name and filename_hint:
        name = filename_hint
    name = _sanitize_filename(name)
    return name or "download.bin"


def _unique_path(output_dir: Path, filename: str) -> Path:
    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem, suffix = filename, ""
    path = output_dir / filename
    counter = 1
    while path.exists():
        path = output_dir / f"{stem}_{counter}{dot}{suffix}"
        counter += 1
    return path


async def _download_to_result(
    url: str,
    allowed_domains: list[str] | None,
    headers: dict[str, str],
    filename_hint: str | None,
    size_limit: int,
    workspace_path: Path,
) -> DownloadResult:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        current_url = url
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                validate_domain(current_url, allowed_domains)
            except DownloadPolicyError as exc:
                return DownloadResult(url=url, success=False, error=str(exc))

            resp = await client.get(current_url, headers=headers)
            if resp.status_code in _REDIRECT_STATUSES:
                location = resp.headers.get("location")
                await resp.aclose()
                if not location:
                    return DownloadResult(url=url, success=False, error="redirect response without Location header")
                current_url = str(httpx.URL(current_url).join(location))
                continue
            break
        else:
            return DownloadResult(url=url, success=False, error="too many redirects")

        if resp.status_code != 200:
            status = resp.status_code
            await resp.aclose()
            return DownloadResult(url=url, success=False, error=f"HTTP {status}")

        content_type = _ext_content_type(resp.headers.get("content-type"))
        final_url = str(resp.url) if resp.url else current_url
        content_length = resp.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > size_limit:
                    await resp.aclose()
                    return DownloadResult(url=url, success=False, error="file exceeds max size limit")
            except ValueError:
                pass

        filename = _infer_filename(resp.headers, final_url, filename_hint)
        if not is_allowed_type(content_type, _ext_of(filename)):
            await resp.aclose()
            return DownloadResult(
                url=url,
                success=False,
                error=f"disallowed content type: {content_type or 'unknown'}",
            )

        digest = hashlib.sha256()
        chunks: list[bytes] = []
        size = 0
        try:
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > size_limit:
                    await resp.aclose()
                    return DownloadResult(url=url, success=False, error="file exceeds max size limit")
                digest.update(chunk)
                chunks.append(chunk)
        finally:
            await resp.aclose()

        output_dir = workspace_outputs_dir(workspace_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = _unique_path(output_dir, filename)
        path.write_bytes(b"".join(chunks))

        return DownloadResult(
            url=url,
            success=True,
            filename=path.name,
            path=str(path),
            size=size,
            sha256=digest.hexdigest(),
            content_type=content_type,
        )


async def download_file(
    url: str,
    allowed_domains: list[str] | None,
    workspace_path: Path,
    filename_hint: str | None = None,
    max_size_mb: int = 50,
) -> DownloadResult:
    headers = {"user-agent": _DEFAULT_USER_AGENT}
    size_limit = max_size_mb * 1024 * 1024
    last_error = "download failed"
    for attempt in range(_MAX_RETRIES + 1):
        try:
            result = await _download_to_result(
                url,
                allowed_domains,
                headers,
                filename_hint,
                size_limit,
                workspace_path,
            )
            return result
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc}"
            logger.warning("download_service network error attempt=%s err=%s", attempt, exc)
            if attempt == _MAX_RETRIES:
                break
    return DownloadResult(url=url, success=False, error=last_error)
