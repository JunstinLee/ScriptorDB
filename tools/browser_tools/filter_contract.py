from __future__ import annotations

"""筛选工具链共享契约（单一事实源）。

filter_detect（探测端）、filter_apply（执行端）、validators（校验端）共用，
避免动作枚举 / 失败标记在多处重复定义导致漂移。
"""

# browser_apply_filter 与面板直连可执行的筛选动作枚举
FILTER_ACTIONS = ("select", "input", "toggle", "set_range", "date_range")

# 筛选执行机制枚举（detect 产出 / apply 分发 / validator 校验共用）
FILTER_MECHANISMS = ("dom_action", "ui_event", "js_table_api")

# JS 表格能力命令白名单（探测端只能产出、执行端只能执行、校验端只能放行）
JS_TABLE_CAPABILITY_KINDS = ("set_filter", "clear_filter")


def is_filter_failure(result: str) -> bool:
    """判定筛选执行结果是否失败（生产者 / 消费者协议）。

    生产者 execute_filter_action 失败时以「失败:」开头；消费者 browser_apply_filter
    据此决定 success 标记与接管触发。统一在此判定，避免各处字符串嗅探不一致。
    """
    return "失败" in result or "failed" in result.lower()
