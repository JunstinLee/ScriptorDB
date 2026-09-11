from __future__ import annotations

import json

from runtime.redact import redact, register_password


# ---- runtime.redact ----


def test_redact_plaintext_and_json_escaped_forms():
    """登记密码的明文与 json 转义形态都被替换。"""
    register_password('p@ss"word\\中')
    # 明文形态
    assert redact("x p@ss\"word\\中 y") == "x [redacted: password] y"
    # json 转义形态（ensure_ascii=False：引号/反斜杠转义、中文原样）
    escaped = json.dumps('p@ss"word\\中', ensure_ascii=False)[1:-1]
    assert redact(f"v={escaped}") == "v=[redacted: password]"
    # json 转义形态（ensure_ascii=True：中文转 \uXXXX）
    ascii_escaped = json.dumps('p@ss"word\\中', ensure_ascii=True)[1:-1]
    assert redact(f"v={ascii_escaped}") == "v=[redacted: password]"


def test_redact_empty_registry_returns_original():
    """未登记任何密码时原样返回（零开销路径）。"""
    text = "plain text, no secrets"
    assert redact(text) is text

