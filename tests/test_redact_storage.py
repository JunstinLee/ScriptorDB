from __future__ import annotations

import json

from pydantic_ai.messages import ModelRequest, ToolCallPart, ToolReturnPart

from runtime.redact import redact, register_password
from runtime.session_file_store import FileSessionStore, _content_to_data, _part_to_data
from runtime.session_model import Session

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


# ---- 落盘脱敏：_part_to_data / _content_to_data ----


def test_part_to_data_redacts_tool_call_dict_args():
    """ToolCallPart 的 dict args 落盘前脱敏，含特殊字符密码也不漏。"""
    register_password('p@ss中"\\')
    part = ToolCallPart(
        tool_name="browser_fill",
        args={"selector": "#password", "text": 'p@ss中"\\'},  # type: ignore[arg-type]
        tool_call_id="c1",
    )
    data = _part_to_data(part)
    assert data is not None
    assert 'p@ss中"\\' not in data["args"]
    assert "[redacted: password]" in data["args"]


def test_part_to_data_redacts_tool_return_content():
    """ToolReturnPart 的 content 落盘前脱敏。"""
    register_password("secret99")
    part = ToolReturnPart(
        tool_name="browser_query",
        content="[redacted: password field]",
        tool_call_id="c1",
    )
    data = _part_to_data(part)
    assert data is not None
    assert "secret99" not in data["content"]


def test_content_to_data_redacts_plain_string():
    """字符串 content 过 _content_to_data 时同样脱敏。"""
    register_password("hunter2")
    assert _content_to_data("pwd=hunter2") == "pwd=[redacted: password]"


def test_part_from_data_keeps_redacted_args_verbatim():
    """回读不二次改写：落盘已脱敏的 args 保持原文（回归 roundtrip）。"""
    from runtime.session_file_store import _part_from_data

    data = {
        "type": "ToolCallPart",
        "tool_call_id": "c1",
        "tool_name": "browser_fill",
        "args": '{"text": "[redacted: password]"}',
    }
    restored = _part_from_data(data)
    assert isinstance(restored, ToolCallPart)
    assert "[redacted: password]" in restored.args


# ---- add_model_messages 不改写（第 6 步回归） ----


def test_add_model_messages_keeps_original_tool_call_args():
    """内存消息保持原始：add_model_messages 不改写 ToolCallPart.args。

    落盘脱敏由 _part_to_data 承担，内存消息须原样回放给模型。
    """
    register_password("secret77")
    session = Session()
    original = ToolCallPart(
        tool_name="browser_fill",
        args={"text": "secret77"},  # type: ignore[arg-type]
        tool_call_id="c1",
    )
    session.add_model_messages([ModelRequest(parts=[original])])  # type: ignore[arg-type]
    kept = session.model_messages[0].parts[0]
    assert isinstance(kept, ToolCallPart)
    assert kept.args == {"text": "secret77"}


# ---- 落盘 roundtrip（含 dict args 与特殊字符密码） ----


def test_session_store_roundtrip_no_plaintext(tmp_path):
    """存盘 JSON 无密码明文；回读的 part 结构完整（内容为脱敏后文本）。"""
    register_password('S3cr3t"值\\')
    storage = tmp_path / "sessions"
    store = FileSessionStore(storage)
    session = store.create()
    session.add_model_messages([  # type: ignore[arg-type]
        ModelRequest(parts=[  # type: ignore[arg-type]
            ToolCallPart(
                tool_name="browser_fill",
                args={"selector": "#password", "text": 'S3cr3t"值\\'},  # type: ignore[arg-type]
                tool_call_id="c1",
            ),
            ToolReturnPart(
                tool_name="browser_query",
                content="[redacted: password field]",
                tool_call_id="c1",
            ),
        ]),
    ])
    store.save()

    # 磁盘 JSON 无明文
    for payload in storage.glob("**/*.json"):
        if "_index" in payload.name:
            continue
        raw = payload.read_text()
        assert 'S3cr3t"值\\' not in raw

    reloaded = FileSessionStore(storage)
    loaded = reloaded.get(session.session_id)
    assert loaded is not None
    first = loaded.model_messages[0]
    assert isinstance(first, ModelRequest)
    call = first.parts[0]
    assert isinstance(call, ToolCallPart)
    assert call.tool_name == "browser_fill"
    assert isinstance(first.parts[1], ToolReturnPart)
