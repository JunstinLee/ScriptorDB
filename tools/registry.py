from __future__ import annotations

from pydantic_ai.toolsets.function import FunctionToolset

_registry: dict[str, FunctionToolset] = {}


def register(name: str, toolset: FunctionToolset) -> None:
    _registry[name] = toolset


def get(name: str) -> FunctionToolset:
    ts = _registry.get(name)
    if ts is None:
        raise KeyError(f"Toolset '{name}' not registered")
    return ts


def get_all() -> list[FunctionToolset]:
    return list(_registry.values())


def list_names() -> list[str]:
    return list(_registry.keys())
