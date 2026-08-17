from __future__ import annotations

import hashlib

from config.settings import Settings
from config.workspace import workspace_outputs_dir
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from schemas.download_models import DownloadManifestEntry
from tools.browser_common import _check_blocked, _require_browser
from tools.download import manifest as download_manifest
from tools.download.service import _sanitize_filename, _unique_path
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.download")

DEFAULT_DOWNLOAD_TIMEOUT = 60
DEFAULT_MAX_SIZE_MB = 50


@db_tool(name="browser_download", category="browser", timeout=90, sequential=True)
async def browser_download(
    ctx: RunContext[Settings],
    url: str = "",
    selector: str = "",
    filename_hint: str = "",
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
    max_size_mb: int = DEFAULT_MAX_SIZE_MB,
) -> str:
    """通过浏览器会话下载文件（登录态自动生效）。

    - 提供 `url`：直接导航到附件地址触发下载（Content-Disposition: attachment）。
    - 提供 `selector`：点击当前页面内的下载按钮/链接触发下载。
    - 文件保存到工作区 outputs 目录，并写入 downloads_manifest.json。
    """
    if not url and not selector:
        return "browser_download requires a url or a selector"

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    workspace_path = ctx.deps.workspace_path if ctx.deps else None
    if workspace_path is None:
        logger.warning("browser_download skipped: no active workspace")
        return "Download failed: no active workspace"

    output_dir = workspace_outputs_dir(workspace_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    download = None
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

    if failure := await download.failure():
        manager.record_action("download", f"failed: {failure}", success=False)
        return f"Download failed: {failure}"

    filename = _sanitize_filename(filename_hint or download.suggested_filename or "download.bin")
    path = _unique_path(output_dir, filename)
    try:
        await download.save_as(path)
    except Exception as e:
        manager.record_action("download", f"save failed: {e}", success=False)
        return f"Download save failed: {e}"

    size = path.stat().st_size
    size_limit = max_size_mb * 1024 * 1024
    if size > size_limit:
        path.unlink(missing_ok=True)
        manager.record_action("download", f"exceeds max size {max_size_mb}MB", success=False)
        return f"Download failed: file exceeds the {max_size_mb}MB size limit"

    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    source_url = url or page.url or ""
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

    manager.record_action("download", f"source={source_url} -> {path.name}", success=True)
    return (
        f"Download successful:\n"
        f"  Filename: {path.name}\n"
        f"  Size: {size} bytes\n"
        f"  SHA-256: {sha256}\n"
        f"  Path: {path}\n"
        f"  Recorded in downloads_manifest.json"
    )
