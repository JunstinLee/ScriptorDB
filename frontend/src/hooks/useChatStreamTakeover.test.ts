import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { useChatStream } from "./useChatStream";
import {
  captureCompleteTakeover,
  makeChatParams,
} from "../test/chatStreamHarness";

const mocks = vi.hoisted(() => ({
  streamChat: vi.fn(),
  attachSessionStream: vi.fn(),
  fetchActiveRun: vi.fn(),
  submitApproval: vi.fn(),
  completeTakeover: vi.fn(),
  cancelTakeover: vi.fn(),
}));

vi.mock("../api/client", () => ({
  streamChat: mocks.streamChat,
  attachSessionStream: mocks.attachSessionStream,
  fetchActiveRun: mocks.fetchActiveRun,
  submitApproval: mocks.submitApproval,
  WorkspaceNotSelectedError: class WorkspaceNotSelectedError extends Error {},
}));

vi.mock("../api/browser", () => ({
  completeTakeover: mocks.completeTakeover,
  cancelTakeover: mocks.cancelTakeover,
  enterHumanControl: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  // 页面挂载的重挂探测：默认无活动 run
  mocks.fetchActiveRun.mockResolvedValue({
    run_id: "",
    suspended: null,
    reason: "",
    last_index: 0,
  });
  mocks.attachSessionStream.mockReturnValue(new AbortController());
});

describe("takeover resume lifecycle", () => {
  it("resets resuming when the resume stream completes", async () => {
    const cb = captureCompleteTakeover(mocks.completeTakeover);
    const { result } = renderHook(() => useChatStream(makeChatParams()));

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
    const cb = captureCompleteTakeover(mocks.completeTakeover);
    const { result } = renderHook(() => useChatStream(makeChatParams()));

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
    mocks.cancelTakeover.mockResolvedValue(undefined);
    const { result } = renderHook(() => useChatStream(makeChatParams()));

    act(() => {
      void result.current.handleTakeoverComplete("sess_1", "done");
    });
    expect(result.current.takeoverInfo.phase).toBe("resuming");

    await act(async () => {
      await result.current.handleTakeoverCancel("sess_1", "run-1");
    });
    expect(result.current.takeoverInfo.phase).toBe("none");
    expect(mocks.cancelTakeover).toHaveBeenCalledWith("sess_1", "run-1");
    await waitFor(() => expect(result.current.takeoverInfo.phase).toBe("none"));
  });
});
