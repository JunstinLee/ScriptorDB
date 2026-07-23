from __future__ import annotations

import importlib
import pkgutil

import tools as _tools_pkg

from tools.registry import register_toolset
from tools.tool_decorators import get_all_tool_defs


def _discover_and_import_all_tool_modules() -> None:
    for _, module_name, _ in pkgutil.iter_modules(_tools_pkg.__path__):
        importlib.import_module(f"tools.{module_name}")


_discover_and_import_all_tool_modules()


@register_toolset("read")
def _create_read_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "read"]


@register_toolset("write")
def _create_write_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "write"]


@register_toolset("viz")
def _create_viz_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "viz"]


@register_toolset("crawl")
def _create_crawl_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "crawl"]


@register_toolset("browser")
def _create_browser_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "browser"]
