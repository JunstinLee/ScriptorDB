from __future__ import annotations

# 组件库可交互标记注册表（通用 + 框架）。
# 取数层（locate_script.LOCATE_ELEMENTS_JS 的 extraInteractive / isOverlay）只消费
# 这里声明的选择器与词根，不写死任何框架名；新增组件库 = 在此追加标记。

# 通用可交互信号（ARIA / tabindex / data-* 交互标记 / 测试属性）——候选扩容粗筛池。
GENERIC_INTERACTIVE_SELECTORS = (
    "[aria-haspopup]",
    "[aria-expanded]",
    "[aria-controls]",
    "[tabindex]",
    "[role]",
    "[data-testid]",
    "[data-test]",
    "[data-qa]",
)

# 供 extraInteractive 判定的交互 ARIA 属性。
INTERACTIVE_ARIA_ATTRS = ("aria-haspopup", "aria-expanded", "aria-controls")

# 组件库可交互 class 词根（JS 侧拼成单个 RegExp）。
INTERACTIVE_CLASS_TOKENS = (
    "picker",
    "calendar",
    "date",
    "dropdown",
    "menu",
    "option",
    "select",
    "tab",
    "switch",
    "checkbox",
    "radio",
    "btn",
    "button",
    "control",
    "trigger",
    "arrow",
    "prev",
    "next",
    "clickable",
    "actionable",
    "toggle",
)

# 覆盖层 / 组件库面板标记：顶层可见时其内部节点视为高优先级候选。
GENERIC_OVERLAY_SELECTORS = (
    "dialog",
    '[role="dialog"]',
    '[role="alertdialog"]',
    '[aria-modal="true"]',
    '[role="menu"]',
    '[role="listbox"]',
    '[role="tree"]',
)

FRAMEWORK_OVERLAY_SELECTORS = (
    '[class*="popover"]',
    '[class*="dropdown"]',
    '[class*="picker-panel"]',
    '[class*="calendar-panel"]',
    '[class*="date-picker"]',
    ".t-popup",
    ".t-dropdown",
    ".t-select__dropdown",
    ".t-date-picker__panel",
    ".ant-picker-dropdown",
    ".ant-select-dropdown",
    ".ant-dropdown",
    ".el-popper",
    ".el-select-dropdown",
    ".el-picker-panel",
)

OVERLAY_SELECTORS = GENERIC_OVERLAY_SELECTORS + FRAMEWORK_OVERLAY_SELECTORS

# JS 侧 RegExp("i") 使用的可交互 class 词根模式。
CLASS_PATTERN = "|".join(INTERACTIVE_CLASS_TOKENS)


def interactive_extra_selector() -> str:
    """候选扩容用的额外选择器（组件库可交互节点粗筛池）。"""
    class_selectors = tuple(f'[class*="{t}"]' for t in INTERACTIVE_CLASS_TOKENS)
    return ",".join(GENERIC_INTERACTIVE_SELECTORS + class_selectors)


def overlay_selector() -> str:
    """活跃覆盖层（弹层 / 下拉 / 日期面板）选择器。"""
    return ",".join(OVERLAY_SELECTORS)
