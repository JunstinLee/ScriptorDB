import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useChatStream } from "./useChatStream";
import type { StreamRunEvent } from "../types";

const { mockStreamChat, mockSubmitApproval, mockCompleteTakeover, mockCancelTakeover } =
  vi.hoisted(() => ({
    mockStreamChat: vi.fn(),
    mockSubmitApproval: vi.fn(),
    mockCompleteTakeover: vi.fn(),
    mockCancelTakeover: vi.fn(),
  }));

vi.mock("../api/client", () => ({
  streamChat: mockStreamChat,
  submitApproval: mockSubmitApproval,
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
  onError: (error: Error) => void;
  onDone: () => void;
};

function captureCompleteTakeover(): CapturedCallbacks {
  let callbacks: CapturedCallbacks | null = null;
  mockCompleteTakeover.mockImplementation(
    (
      _sid: string,
      _result: string,
      onDone: () => void,
      onError: (e: Error) => void,
    ) => {
      callbacks = { onDone, onError };
      return new AbortController();
    },
  );
  return {
    get onError() {
      return callbacks!.onError;
    },
    get onDone() {
      return callbacks!.onDone;
    },
  };
}
type ApprovalRequestLike = {
  type: "approval_request";
  run_id: string;
  request_id: string;
  calls: Array<{ tool_call_id: string; tool_name: string; args: Record<string, unknown> }>;
};

function captureApprovalRequest(): {
  setApprovalRequest: (e: ApprovalRequestLike) => void;
} {
  let approvalCb: ((e: ApprovalRequestLike) => void) | null = null;
  mockStreamChat.mockImplementation(
    (
      _sid: string,
      _body: unknown,
      _onEvent: unknown,
      _onError: unknown,
      _onDone: unknown,
      onApprovalRequest?: (e: ApprovalRequestLike) => void,
    ) => {
      approvalCb = onApprovalRequest ?? null;
      return new AbortController();
    },
  );
  return {
    setApprovalRequest: (e: ApprovalRequestLike) => approvalCb!(e),
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
      cb.onDone();
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
describe("approval submit", () => {
  it("signals approval via short POST without local terminal events", async () => {
    mockSubmitApproval.mockResolvedValue(undefined);
    const stream = captureApprovalRequest();
    const params = makeParams();
    const { result } = renderHook(() => useChatStream(params));

    act(() => {
      void result.current.handleSend("hi", [], null);
    });
    act(() => {
      stream.setApprovalRequest({
        type: "approval_request",
        run_id: "run-1",
        request_id: "req-1",
        calls: [
          {
            tool_call_id: "c1",
            tool_name: "browser_apply_filter",
            args: { action: "select", target: "Status", value: "Active" },
          },
        ],
      });
    });

    await act(async () => {
      await result.current.handleApprovalSubmit(true);
    });
    expect(mockSubmitApproval).toHaveBeenCalledWith(
      "sess_1",
      "req-1",
      { c1: true },
      undefined,
    );
    // 不再本地合成 tool_result/run_end：原流继续推送后续事件
    expect(params.appendEvent).not.toHaveBeenCalled();
    expect(params.setLoading).not.toHaveBeenCalledWith(false);
  });

  it("signals denial through the same short POST", async () => {
    mockSubmitApproval.mockResolvedValue(undefined);
    const stream = captureApprovalRequest();
    const params = makeParams();
    const { result } = renderHook(() => useChatStream(params));

    act(() => {
      void result.current.handleSend("hi", [], null);
    });
    act(() => {
      stream.setApprovalRequest({
        type: "approval_request",
        run_id: "run-1",
        request_id: "req-2",
        calls: [
          {
            tool_call_id: "c2",
            tool_name: "browser_apply_filter",
            args: { action: "input", target: "Query", value: "x" },
          },
        ],
      });
    });

    await act(async () => {
      await result.current.handleApprovalSubmit(false);
    });
    expect(mockSubmitApproval).toHaveBeenCalledWith(
      "sess_1",
      "req-2",
      { c2: false },
      undefined,
    );
    expect(params.appendEvent).not.toHaveBeenCalled();
    expect(params.setLoading).not.toHaveBeenCalledWith(false);
  });
});
