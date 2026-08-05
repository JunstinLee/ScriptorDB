from __future__ import annotations

from pydantic_ai import RunContext

from config.settings import Settings
from config.workspace import workspace_outputs_dir
from schemas.download_models import DownloadManifestEntry
from services import download_manifest
from services.download_service import download_file as download_service_download_file
from tools.tool_decorators import db_tool


def _parse_domains(raw: str) -> list[str] | None:
    domains = [d.strip() for d in raw.split(",") if d.strip()]
    return domains or None


@db_tool(name="download_file", category="download", timeout=60)
async def download_file(
    ctx: RunContext[Settings],
    url: str,
    allowed_domains: str = "",
    filename_hint: str = "",
    max_size_mb: int = 50,
) -> str:
    workspace_path = ctx.deps.workspace_path if ctx.deps else None
    if workspace_path is None:
        return "下载失败: 没有活动工作区，请先选择工作区"

    domains = _parse_domains(allowed_domains)
    result = await download_service_download_file(
        url,
        domains,
        workspace_path,
        filename_hint=filename_hint or None,
        max_size_mb=max_size_mb,
    )
    if not result.success:
        return f"下载失败: {result.error}"

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
        f"下载成功:\n"
        f"  文件名: {result.filename}\n"
        f"  大小: {result.size} bytes\n"
        f"  SHA-256: {result.sha256}\n"
        f"  保存路径: {result.path}\n"
        f"  已写入来源清单 (downloads_manifest.json)"
    )
