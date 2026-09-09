from __future__ import annotations

import json

_registered: set[str] = set()

_REDACTED = "[redacted: password]"


def register_password(password: str) -> None:
    """登记需要脱敏的密码；空串/None 忽略。"""
    if not password:
        return
    _registered.add(password)


def registered_passwords() -> frozenset[str]:
    return frozenset(_registered)


def redact(text: str) -> str:
    """替换登记集合中每个密码的明文形态与 json 转义形态。

    json 转义形态覆盖 `json.dumps(p)[1:-1]` 与 `ensure_ascii=False` 变体
    （落盘序列化用 ensure_ascii=False：非 ASCII 保留原样、引号/反斜杠转义；
    默认 ensure_ascii=True 会把非 ASCII 转成 \\uXXXX）。按长度降序替换，
    避免短形态先替换破坏长形态的匹配。集合为空时原样返回。
    """
    if not _registered:
        return text
    for pwd in sorted(_registered, key=len, reverse=True):
        forms = {
            pwd,
            json.dumps(pwd, ensure_ascii=False)[1:-1],
            json.dumps(pwd, ensure_ascii=True)[1:-1],
            # 完整 json.dumps 含外层引号：evaluate 结果经 json.dumps 后
            # 密码是带引号串（"SuperSecretPassword!"），仅替换裸/去引号
            # 形态不命中。
            json.dumps(pwd, ensure_ascii=False),
            json.dumps(pwd, ensure_ascii=True),
        }
        for form in sorted(forms, key=len, reverse=True):
            if form and form in text:
                text = text.replace(form, _REDACTED)
    return text
