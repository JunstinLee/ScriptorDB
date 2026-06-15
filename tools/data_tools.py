from __future__ import annotations

import csv
import glob as glob_mod
import json
import os

from pydantic_ai import RunContext

from config.settings import Settings
from tools.errors import _to_tool_error
from tools.tool_result import ToolErrorInfo, ToolResult


def read_csv(
    ctx: RunContext[Settings],
    filepath: str,
    preview_rows: int = 10,
    encoding: str = "utf-8",
) -> ToolResult:
    if not os.path.isfile(filepath):
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )

    try:
        with open(filepath, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
            preview: list[list[str]] = []
            row_count = 0
            for row in reader:
                row_count += 1
                if len(preview) < preview_rows:
                    preview.append(row)

        return ToolResult(
            success=True,
            output=f"读取 {os.path.basename(filepath)}: {row_count} 行, {len(headers)} 列",
            data={
                "file": filepath,
                "columns": headers,
                "rows": row_count,
                "preview": preview,
            },
        )
    except FileNotFoundError:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )
    except Exception as e:
        return _to_tool_error(e)


def write_csv(
    ctx: RunContext[Settings],
    filepath: str,
    columns: list[str],
    data: list[list[str]],
    encoding: str = "utf-8",
) -> ToolResult:
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding=encoding, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(data)

        return ToolResult(
            success=True,
            output=f"写入 {len(data)} 行到 {os.path.basename(filepath)}",
            data={"file": filepath, "rows_written": len(data)},
        )
    except Exception as e:
        return _to_tool_error(e)


def read_file(
    ctx: RunContext[Settings],
    filepath: str,
    max_size_kb: int = 50,
    encoding: str = "utf-8",
) -> ToolResult:
    if not os.path.isfile(filepath):
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )

    try:
        size = os.path.getsize(filepath)
        truncated = size > max_size_kb * 1024

        with open(filepath, "r", encoding=encoding) as f:
            content = f.read(max_size_kb * 1024) if truncated else f.read()

        ext = os.path.splitext(filepath)[1].lower()
        extra: dict = {"file": filepath, "size_bytes": size, "truncated": truncated}

        if ext == ".json":
            try:
                parsed = json.loads(content)
                extra["parsed"] = True
                extra["json_keys"] = list(parsed.keys()) if isinstance(parsed, dict) else None
                output = f"JSON 文件 {os.path.basename(filepath)}{'（已截断）' if truncated else ''}"
                return ToolResult(success=True, output=output, data=extra)
            except json.JSONDecodeError:
                pass

        output = f"文件 {os.path.basename(filepath)}: {size} bytes{'（已截断）' if truncated else ''}"
        return ToolResult(success=True, output=output, data=extra | {"content": content})
    except Exception as e:
        return _to_tool_error(e)


def write_file(
    ctx: RunContext[Settings],
    filepath: str,
    content: str,
    encoding: str = "utf-8",
) -> ToolResult:
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)

        return ToolResult(
            success=True,
            output=f"写入 {len(content)} 字符到 {os.path.basename(filepath)}",
            data={"file": filepath, "chars_written": len(content)},
        )
    except Exception as e:
        return _to_tool_error(e)


def list_files(
    ctx: RunContext[Settings],
    directory: str = ".",
    pattern: str = "*",
) -> ToolResult:
    try:
        search_path = os.path.join(directory, pattern)
        files = sorted(glob_mod.glob(search_path))
        result_files: list[dict] = []
        for f in files[:100]:
            try:
                st = os.stat(f)
                result_files.append({
                    "name": f,
                    "size_bytes": st.st_size,
                    "is_dir": os.path.isdir(f),
                })
            except OSError:
                result_files.append({"name": f, "size_bytes": 0, "is_dir": False})

        return ToolResult(
            success=True,
            output=f"{len(files)} 个文件/目录匹配 {pattern}",
            data={
                "directory": directory,
                "pattern": pattern,
                "count": min(len(files), 100),
                "files": result_files,
            },
        )
    except Exception as e:
        return _to_tool_error(e)
