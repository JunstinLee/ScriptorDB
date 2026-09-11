import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useChatStream } from "./useChatStream";
import {
  captureApprovalRequest,
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
  mocks.fetchActiveRun.mockResolvedValue({
    run_id: "",
    suspended: null,
    reason: "",
    last_index: 0,
  });
  mocks.attachSessionStream.mockReturnValue(new AbortController());
});

describe("approval submit", () => {
  it("signals approval via short POST without local terminal events", async () => {
    mocks.submitApproval.mockResolvedValue(undefined);
    const stream = captureApprovalRequest(mocks.streamChat);
    const params = makeChatParams();
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
    expect(mocks.submitApproval).toHaveBeenCalledWith(
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
    mocks.submitApproval.mockResolvedValue(undefined);
    const stream = captureApprovalRequest(mocks.streamChat);
    const params = makeChatParams();
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
    expect(mocks.submitApproval).toHaveBeenCalledWith(
      "sess_1",
      "req-2",
      { c2: false },
      undefined,
    );
    expect(params.appendEvent).not.toHaveBeenCalled();
    expect(params.setLoading).not.toHaveBeenCalledWith(false);
  });
});
