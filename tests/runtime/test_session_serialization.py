"""session_model 消息序列化 roundtrip：工具调用/返回 part 与文本 part。"""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

from runtime.session_file_store import FileSessionStore


def test_model_message_serialization_roundtrip_tool_parts(tmp_path):
    storage = tmp_path / "sessions"
    store = FileSessionStore(storage)
    session = store.create()
    session.add_model_messages([
        ModelRequest(parts=[
            ToolCallPart(tool_name="browser_click", args={"selector": "#a"}, tool_call_id="c1"),  # type: ignore[arg-type]
            ToolReturnPart(tool_name="browser_click", content="clicked", tool_call_id="c1"),
        ]),
        ModelResponse(parts=[TextPart(content="hello")]),
    ])
    store.save()

    reloaded = FileSessionStore(storage)
    loaded = reloaded.get(session.session_id)
    assert loaded is not None
    msgs = loaded.model_messages
    assert len(msgs) == 2
    first = msgs[0]
    assert isinstance(first, ModelRequest)
    assert isinstance(first.parts[0], ToolCallPart)
    assert first.parts[0].tool_name == "browser_click"
    assert first.parts[0].tool_call_id == "c1"
    assert isinstance(first.parts[1], ToolReturnPart)
    assert first.parts[1].content == "clicked"
    second = msgs[1]
    assert isinstance(second, ModelResponse)
    assert isinstance(second.parts[0], TextPart)
    assert second.parts[0].content == "hello"
