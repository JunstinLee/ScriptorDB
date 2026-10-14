from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext

from config.settings import Settings
from config.workspace import workspace_outputs_dir
from core.logging_setup import get_logger
from schemas.download_models import DownloadManifestEntry
from tools.download import manifest as download_manifest
from tools.download.service import _sanitize_filename, _unique_path
from tools.download.service import download_file as download_service_download_file
from tools.tool_decorators import db_tool

logger = get_logger("tools.download")

DEFAULT_BROWSER_DOWNLOAD_TIMEOUT = 60
DEFAULT_MAX_SIZE_MB = 50
_BROWSER_DOWNLOAD_TOOL_TIMEOUT = 90


def _parse_domains(raw: str) -> list[str] | None:
    domains = [d.strip() for d in raw.split(",") if d.strip()]
    return domains or None


async def _save_browser_download(
    download: Any,
    output_dir: Path,
    filename_hint: str = "",
    max_size_mb: int = DEFAULT_MAX_SIZE_MB,
    source_url: str = "",
) -> str:
    """保存 Playwright Download 到 output_dir，返回成功描述或失败原因。"""
    if failure := await download.failure():
        return f"Download failed: {failure}"

    filename = _sanitize_filename(filename_hint or download.suggested_filename or "download.bin")
    path = _unique_path(output_dir, filename)
    try:
        await download.save_as(path)
    except Exception as e:
        return f"Download save failed: {e}"

    size = path.stat().st_size
    size_limit = max_size_mb * 1024 * 1024
    if size > size_limit:
        path.unlink(missing_ok=True)
        return f"Download failed: file exceeds the {max_size_mb}MB size limit"

    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    download_manifest.append(
        DownloadManifestEntry(
            source_url=source_url,
            title="",
            publish_date="",
            filename=path.name,
            size=size,
            sha256=sha256,
        ),
        download_manifest.manifest_path(output_dir),
    )
    return (
        f"Download successful:\n"
        f"  Filename: {path.name}\n"
        f"  Size: {size} bytes\n"
        f"  SHA-256: {sha256}\n"
        f"  Path: {path}\n"
        f"  Recorded in downloads_manifest.json"
    )


async def _download_via_http(
    ctx: RunContext[Settings],
    url: str,
    allowed_domains: str,
    filename_hint: str,
    max_size_mb: int,
) -> str:
    workspace_path = ctx.deps.workspace_path if ctx.deps else None
    if workspace_path is None:
        logger.warning("download_file skipped: no active workspace")
        return "Download failed: no active workspace"
    if not url:
        return "download_file requires a url"

    domains = _parse_domains(allowed_domains)
    result = await download_service_download_file(
        url,
        domains,
        workspace_path,
        filename_hint=filename_hint or None,
        max_size_mb=max_size_mb,
    )
    if not result.success:
        return f"Download failed: {result.error}"

    manifest_path = download_manifest.manifest_path(workspace_outputs_dir(workspace_path))
    download_manifest.append(
        DownloadManifestEntry(
            source_url=url,
            title="",
            publish_date="",
            filename=result.filename or "",
            size=result.size or 0,
            sha256=result.sha256 or "",
        ),
        manifest_path,
    )
    return (
        f"Download successful:\n"
        f"  Filename: {result.filename}\n"
        f"  Size: {result.size} bytes\n"
        f"  SHA-256: {result.sha256}\n"
        f"  Path: {result.path}\n"
        f"  Recorded in downloads_manifest.json"
    )


async def _download_via_browser(
    ctx: RunContext[Settings],
    url: str,
    selector: str,
    filename_hint: str,
    timeout: int,
    max_size_mb: int,
) -> str:
    if not url and not selector:
        return "browser download requires a url or a selector"

    from tools.browser_common import _check_blocked, _require_browser

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    workspace_path = ctx.deps.workspace_path if ctx.deps else None
    if workspace_path is None:
        logger.warning("download_file skipped: no active workspace")
        return "Download failed: no active workspace"

    output_dir = workspace_outputs_dir(workspace_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    async def _trigger() -> str:
        trigger_error: Exception | None = None
        try:
            async with page.expect_download(timeout=timeout * 1000) as dl_info:
                try:
                    if url:
                        await page.goto(url, wait_until="commit")
                    else:
                        await page.click(selector)
                except Exception as e:  # 导航可能因下载中断而抛错，下载事件本身仍会触发
                    trigger_error = e
                download = await dl_info.value
        except Exception as e:
            manager.record_action("download", f"trigger failed: {trigger_error or e}", success=False)
            return f"Download trigger failed: {trigger_error or e}"

        result = await _save_browser_download(
            download,
            output_dir,
            filename_hint=filename_hint,
            max_size_mb=max_size_mb,
            source_url=url or page.url or "",
        )
        if result.startswith("Download successful"):
            manager.record_action("download", f"source={url or page.url or ''} -> saved", success=True)
        else:
            manager.record_action("download", result, success=False)
        return result

    manager.tool_started()
    try:
        return await asyncio.wait_for(_trigger(), timeout=_BROWSER_DOWNLOAD_TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        manager.record_action("download", "browser download timed out", success=False)
        return (
            f"Download failed: browser download timed out after "
            f"{_BROWSER_DOWNLOAD_TOOL_TIMEOUT} seconds; the operation did not complete."
        )
    finally:
        manager.tool_finished()


@db_tool(name="download_file", category="download", timeout=90, sequential=True)
async def download_file(
    ctx: RunContext[Settings],
    url: str = "",
    selector: str = "",
    allowed_domains: str = "",
    filename_hint: str = "",
    timeout: int = DEFAULT_BROWSER_DOWNLOAD_TIMEOUT,
    max_size_mb: int = DEFAULT_MAX_SIZE_MB,
    use_browser: bool = False,
) -> str:
    """Download a file over HTTP or through the live browser session.

    - `use_browser=False` (default): HTTP fetch; `url` is required and
      `allowed_domains` (comma-separated) restricts which hosts are allowed.
    - `use_browser=True`: download through the browser so the logged-in state
      applies; pass `url` to navigate to the attachment, or `selector` to click
      a download control on the current page.

    Files are saved to the workspace outputs directory and recorded in
    downloads_manifest.json.
    """
    if use_browser:
        return await _download_via_browser(ctx, url, selector, filename_hint, timeout, max_size_mb)
    return await _download_via_http(ctx, url, allowed_domains, filename_hint, max_size_mb)
