"""browser_find 重复调用熔断。

同一逻辑 run、同一页、同一导航修订、同一查询指纹已被成功回答过，模型再发一次
相同的 browser_find 只会得到同样结果——改用已拿到的 ref。空查询（无 text/role）
与 containers 模式不参与熔断：前者常用于「重新看一眼整页」，后者不产出 ref。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE

logger = get_logger("tool_middleware")


def record_find(
    ctx,
    *,
    page_key: str,
    page_url: str,
    nav_rev: int,
    fingerprint: str,
    produced: bool,
) -> None:
    """记录一次 browser_find 的结果（由工具层在产出 ref 后回写）。"""
    run_key = ctxmod._run_key(ctx)
    STATE.add_find(run_key, {
        "page_key": page_key,
        "page_url": page_url,
        "nav_rev": nav_rev,
        "fingerprint": fingerprint,
        "produced": produced,
    })


def clear_run(run_key: str) -> None:
    """run 终结时清理该 run 的 find 记录，避免跨 run 累积。"""
    STATE.clear_run(run_key)


def _is_repeat_find(ctx, args: dict | None) -> bool:
    """同一 run / 页 / 导航修订 / 查询指纹上是否已有成功 find 记录。

    不确定（取不到 run 或 page）一律返回 ``False``（fail-open）。
    """
    run_key = ctxmod._run_key(ctx)
    if not run_key:
        return False
    try:
        manager = ctxmod._manager()
    except Exception:
        return False
    page_key = ctxmod._page_key(manager)
    if not page_key:
        return False
    page_url = ctxmod._page_url(manager)
    nav_rev = ctxmod._nav_revision(manager)

    raw_mode = args.get("mode") if isinstance(args, dict) else None
    mode = (str(raw_mode) if raw_mode else "elements").strip().lower()
    if mode != "elements":
        # containers 模式是另一种查询，且不产出 ref，不参与熔断。
        return False

    text = str(args.get("text") or "") if isinstance(args, dict) else ""
    role = str(args.get("role") or "") if isinstance(args, dict) else ""
    # 空查询（无 text/role）不参与熔断：它常用于"重新看一眼整页"，页面换状态后
    # 本就需要重扫，拦下来只会把模型推向未受管控的裸 JS 路径。
    if not ctxmod._normalize_query_part(text) and not ctxmod._normalize_query_part(role):
        return False
    raw_scope = args.get("scope") if isinstance(args, dict) else None
    scope = (str(raw_scope) if raw_scope else "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"
    content_rev = ctxmod._content_revision(manager)
    fingerprint = ctxmod._find_fingerprint(text, role, scope, content_rev)

    records = STATE.get_finds(run_key)
    for record in records:
        if not record.get("produced"):
            continue
        if (
            record.get("page_key") == page_key
            and record.get("nav_rev") == nav_rev
            and record.get("page_url") == page_url
            and record.get("fingerprint") == fingerprint
        ):
            return True

    # 弱命中：同一 run / 页 / 导航修订 / URL，text+role 归一化后相同、两次均
    # produced，仅 scope 不同 → 仍是同一意图的重复重扫（模型常把 scope 升级
    # visible → container → page 当重试阶梯）。page_url / nav_rev 变化仍放行。
    scope_fingerprints = {
        ctxmod._find_fingerprint(text, role, candidate_scope, content_rev)
        for candidate_scope in ("visible", "container", "page")
    }
    for record in records:
        if not record.get("produced"):
            continue
        if (
            record.get("page_key") == page_key
            and record.get("nav_rev") == nav_rev
            and record.get("page_url") == page_url
            and record.get("fingerprint") in scope_fingerprints
        ):
            return True

    # 重叠命中：同一 run / 页 / 导航修订 / URL、旧记录已 produced，新查询与旧指纹
    # 虽不完全相同，但 role 归一化后相同、或 text 互为子串 → 视为同一意图的重复
    # 重扫（模型常把 role 换成 text 或收窄 text 当作重试）。指纹格式为
    # ``scope||role||text||content_rev``。
    new_text = ctxmod._normalize_query_part(text)
    new_role = ctxmod._normalize_query_part(role)
    for record in records:
        if not record.get("produced"):
            continue
        if (
            record.get("page_key") != page_key
            or record.get("nav_rev") != nav_rev
            or record.get("page_url") != page_url
        ):
            continue
        parts = str(record.get("fingerprint", "")).split("||")
        if len(parts) != 4:
            continue
        old_role, old_text = parts[1], parts[2]
        if new_role and new_role == old_role:
            return True
        if new_text and old_text and (new_text in old_text or old_text in new_text):
            return True
    return False


class FindRepeatPolicy:
    """拦截同一查询指纹上重复的 browser_find。"""

    name = "find-repeat"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        if tool_name != "browser_find":
            return None
        if _is_repeat_find(ctx, args):
            logger.info(
                "tool middleware: blocking browser_find (find-repeat) — run %s",
                ctxmod._run_key(ctx),
            )
            return "find-repeat"
        return "allow"
