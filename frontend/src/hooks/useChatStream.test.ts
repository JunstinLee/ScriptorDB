import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useChatStream } from "./useChatStream";
import type { StreamRunEvent } from "../types";

const { mockStreamChat, mockStreamApproval, mockCompleteTakeover, mockCancelTakeover } =
  vi.hoisted(() => ({
    mockStreamChat: vi.fn(),
    mockStreamApproval: vi.fn(),
    mockCompleteTakeover: vi.fn(),
    mockCancelTakeover: vi.fn(),
  }));

vi.mock("../api/client", () => ({
  streamChat: mockStreamChat,
  streamApproval: mockStreamApproval,
  WorkspaceNotSelectedError: class WorkspaceNotSelectedError extends Error {},
}));

vi.mock("../api/browser", () => ({
  completeTakeover: mockCompleteTakeover,
  cancelTakeover: mockCancelTakeover,
  enterHumanControl: vi.fn(),
}));

function makeParams(overrides: Partial<ReturnType<typeof makeParams>> = {}) {
  return {
    activeSessionId: "sess_1",
    addUserMessage: vi.fn(),
    appendEvent: vi.fn(),
    appendAction: vi.fn(),
    appendStreamingText: vi.fn(),
    createNewSession: vi.fn(async () => "sess_1"),
    finalizeAssistantMessage: vi.fn(),
    handleWorkspaceMissing: vi.fn(),
    refreshSessionTitle: vi.fn(async () => {}),
    refreshUndo: vi.fn(async () => {}),
    setLoading: vi.fn(),
    selectedModel: "model-1",
    selectedProvider: "openai",
    onBrowserActivity: vi.fn(),
    setBrowserActive: vi.fn(),
    setActiveMainTab: vi.fn(),
    ...overrides,
  };
}

type CapturedCallbacks = {
  onEvent: (event: StreamRunEvent) => void;
  onError: (error: Error) => void;
  onDone: (fullOutput: string) => void;
};

function captureCompleteTakeover(): CapturedCallbacks {
  let callbacks: CapturedCallbacks | null = null;
  mockCompleteTakeover.mockImplementation(
    (
      _sid: string,
      _result: string,
      onEvent: (e: StreamRunEvent) => void,
      onDone: (o: string) => void,
      onError: (e: Error) => void,
    ) => {
      callbacks = { onEvent, onError, onDone };
      return new AbortController();
    },
  );
  return {
    get onEvent() {
      return callbacks!.onEvent;
    },
    get onError() {
      return callbacks!.onError;
    },
    get onDone() {
      return callbacks!.onDone;
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("takeover resume lifecycle", () => {
  it("resets resuming when the resume stream completes", async () => {
    const cb = captureCompleteTakeover();
    const { result } = renderHook(() => useChatStream(makeParams()));

    act(() => {
      void result.current.handleTakeoverComplete("sess_1", "done");
    });
    expect(result.current.takeoverInfo.phase).toBe("resuming");

    act(() => {
      cb.onDone("final output");
    });
    expect(result.current.takeoverInfo.phase).toBe("none");
    expect(result.current.takeoverInfo.runId).toBe("");
  });

  it("resets resuming when the resume stream errors", async () => {
    const cb = captureCompleteTakeover();
    const { result } = renderHook(() => useChatStream(makeParams()));

    act(() => {
      void result.current.handleTakeoverComplete("sess_1", "done");
    });
    expect(result.current.takeoverInfo.phase).toBe("resuming");

    act(() => {
      cb.onError(new Error("boom"));
    });
    expect(result.current.takeoverInfo.phase).toBe("none");
  });

  it("resets resuming when the user cancels the takeover", async () => {
    mockCancelTakeover.mockResolvedValue(undefined);
    const { result } = renderHook(() => useChatStream(makeParams()));

    act(() => {
      void result.current.handleTakeoverComplete("sess_1", "done");
    });
    expect(result.current.takeoverInfo.phase).toBe("resuming");

    await act(async () => {
      await result.current.handleTakeoverCancel("sess_1", "run-1");
    });
    expect(result.current.takeoverInfo.phase).toBe("none");
    expect(mockCancelTakeover).toHaveBeenCalledWith("sess_1", "run-1");
    await waitFor(() => expect(result.current.takeoverInfo.phase).toBe("none"));
  });
});
