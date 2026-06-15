import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatMessages } from "./useChatMessages";

describe("useChatMessages", () => {
  it("starts with empty messages", () => {
    const { result } = renderHook(() => useChatMessages());
    expect(result.current.messages).toEqual([]);
  });

  it("adds a user message", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.addUserMessage("Hello");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "Hello",
    });
    expect(result.current.messages[0].timestamp).toBeTruthy();
  });

  it("appendStreamingText creates assistant message on first call", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.appendStreamingText("Hi");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("assistant");
    expect(result.current.messages[0].content).toBe("Hi");
  });

  it("appendStreamingText appends to existing assistant message", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.appendStreamingText("Hello");
    });
    act(() => {
      result.current.appendStreamingText(" World");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].content).toBe("Hello World");
  });

  it("appendStreamingText creates new assistant after user message", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.addUserMessage("Q");
    });
    act(() => {
      result.current.appendStreamingText("A1");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[1].role).toBe("assistant");
  });

  it("finalizeAssistantMessage replaces content of last assistant", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.appendStreamingText("H");
    });
    act(() => {
      result.current.appendStreamingText("e");
    });
    act(() => {
      result.current.finalizeAssistantMessage("Hello");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].content).toBe("Hello");
  });

  it("finalizeAssistantMessage does nothing when last message is not assistant", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.addUserMessage("Hi");
    });
    act(() => {
      result.current.finalizeAssistantMessage("should not appear");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
  });

  it("setMessages replaces all messages", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.setMessages([
        {
          role: "assistant",
          content: "Hello",
          timestamp: "2025-01-01T00:00:00Z",
        },
      ]);
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].content).toBe("Hello");
  });
});
