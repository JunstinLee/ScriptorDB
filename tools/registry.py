from __future__ import annotations

from collections.abc import Callable


class _ToolsetRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[], list]] = {}

    def register(self, name: str, factory: Callable):
        self._factories[name] = factory

    def discover(self, exclude_categories: set[str] | None = None) -> list:
        result = []
        exclude = exclude_categories or set()
        for name, factory in self._factories.items():
            if name in exclude:
                continue
            result.extend(factory())
        return result


registry = _ToolsetRegistry()


def register_toolset(name: str):
    def decorator(fn):
        registry.register(name, fn)
        return fn
    return decorator


def get_all_tools(exclude_categories: set[str] | None = None) -> list:
    return registry.discover(exclude_categories)
