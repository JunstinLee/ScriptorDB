"""中间件共享上下文：run/round 身份、当前页读取、find 指纹与工具查找。

这些 helper 只做「读」，不持有状态（状态在 :mod:`runtime.middleware.state`）。
刻意保留模块级函数而非类方法：策略模块通过模块属性（``ctxmod._manager()``）
间接调用，测试可对单一入口 monkeypatch。
"""

from __future__ import annotations

from typing import Any


def _round_key(ctx) -> str:
    return getattr(ctx, "run_id", None) or "default-round"


def _run_key(ctx) -> str:
    """一次逻辑 run 的稳定身份。

    取 ``ctx.deps.run_id``（由 lifecycle 在每次 agent.run 前写入 RunTracker 的
    run_id，贯穿审批暂停/恢复的续跑循环），退化到 pydantic 的 ``ctx.run_id``
    （每次 agent.run 都会变，仅作兜底）。不要复用 ``_round_key``。
    """
    deps = getattr(ctx, "deps", None)
    run_id = getattr(deps, "run_id", None) if deps is not None else None
    if run_id:
        return str(run_id)
    return getattr(ctx, "run_id", None) or "default-round"


def _manager():
    from browser import get_manager

    return get_manager()


def _page_key(manager) -> str:
    """当前活动页身份；无页面返回 ``""``（上层 fail-open）。"""
    try:
        page = manager.page()
    except Exception:
        return ""
    return str(id(page)) if page is not None else ""


def _nav_revision(manager) -> int:
    """当前活动页的导航修订计数；读取失败按 0 处理。"""
    try:
        return int(manager.nav_revision())
    except Exception:
        return 0


def _content_revision(manager) -> int:
    """当前活动页的内容修订计数；读取失败或 manager 不支持时按 0 处理。"""
    try:
        return int(manager.content_revision())
    except Exception:
        return 0


def _page_url(manager) -> str:
    """当前活动页 URL；无页面返回 ``""``。"""
    try:
        page = manager.page()
    except Exception:
        return ""
    return (getattr(page, "url", "") or "") if page is not None else ""


def _normalize_query_part(value: Any) -> str:
    """归一化 browser_find 的 text / role：折叠连续空白并小写。"""
    return " ".join(str(value or "").split()).lower()


def _find_fingerprint(text: str, role: str, scope: str, content_rev: int = 0) -> str:
    """把 browser_find 的查询参数组装为稳定指纹。

    ``text`` / ``role`` 归一化（去首尾空白、折叠连续空白、小写），使同一意图的
    大小写 / 空白变体归为同一条；``scope`` 保留原值 —— visible / container / page
    语义不同，合并会误拦合法的扩大重扫。末尾追加内容修订号：同一 URL 下页面内容
    已被动作工具更换（内容修订推进）时指纹随之变化，不再误判为重复重扫。
    """
    return (
        f"{scope}||{_normalize_query_part(role)}||{_normalize_query_part(text)}"
        f"||{int(content_rev or 0)}"
    )


def _is_browser_tool(tool_name: str) -> bool:
    return tool_name.startswith("browser_")


def _find_tool_func(name: str):
    from tools.tool_decorators import get_all_tool_defs

    for tool_def in get_all_tool_defs():
        if tool_def.name == name:
            return tool_def.func
    return None
