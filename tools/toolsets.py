from __future__ import annotations

import importlib
import pkgutil

import tools as _tools_pkg

from core.logging_setup import get_logger
from tools.registry import register_toolset
from tools.tool_decorators import get_all_tool_defs

logger = get_logger("tools.toolsets")

# Subsystems backed by optional extras. They must not be imported by the blanket
# scan: `tools.browser` / `tools.browser_common` / `tools.browser_tools` pull in
# playwright, and `tools.crawl` pulls in beautifulsoup4 + markdownify. Each is
# imported on demand from its own toolset factory instead.
_OPTIONAL_SUBSYSTEMS = frozenset({"browser", "browser_common", "browser_tools", "crawl"})


def _import_optional(module: str) -> bool:
    """Import an optional subsystem; degrade to "no tools" when its extra is absent."""
    try:
        importlib.import_module(module)
    except ImportError as e:
        logger.info("optional subsystem %s unavailable — its tools are disabled: %s", module, e)
        return False
    return True


def _discover_and_import_all_tool_modules() -> None:
    for _, module_name, _ in pkgutil.iter_modules(_tools_pkg.__path__):
        if module_name in _OPTIONAL_SUBSYSTEMS:
            continue
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
    _import_optional("tools.crawl")
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "crawl"]


@register_toolset("browser")
def _create_browser_toolset():
    _import_optional("tools.browser")
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "browser"]


@register_toolset("download")
def _create_download_toolset():
    return [d.to_tool() for d in get_all_tool_defs() if d.category == "download"]
