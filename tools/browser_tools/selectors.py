from __future__ import annotations

import re

# Playwright 引擎选择器前缀（text=/xpath=/aria= 等）不是合法 CSS，
# 不能传给 document.querySelector —— 高亮/跟踪前先识别并跳过。
_PLAYWRIGHT_ENGINES = frozenset({
    "css", "xpath", "text", "id", "data-testid", "data-test", "data-test-id",
    "data-qa", "aria", "role", "nth", "internal",
})

# 动作层超时 = 工具超时（15s）- 余量：避免 Playwright 默认 30s 与 wrapper 同时到点。
_ACTION_TIMEOUT_MS = 12_000

# :has-text("…") / :contains("…") 是 Playwright 伪类选择器，同样不是合法 CSS，
# document.querySelector 会抛 SyntaxError；与 text= 等前缀式引擎选择器一样按引擎处理跳过。
_PLAYWRIGHT_PSEUDO_RE = re.compile(r":(?:has-text|contains)\(")


def _is_engine_selector(selector: str) -> bool:
    match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*?)\s*=", selector)
    if match and match.group(1).lower() in _PLAYWRIGHT_ENGINES:
        return True
    return bool(_PLAYWRIGHT_PSEUDO_RE.search(selector))


_CONTAINS_RE = re.compile(r""":contains\(\s*(['"])(.*?)\1\s*\)""")


def _normalize_selector(selector: str) -> str:
    """把 jQuery 的 :contains("x") 归一化为 Playwright 的 :has-text("x")。"""
    return _CONTAINS_RE.sub(lambda m: f':has-text("{m.group(2)}")', selector)
