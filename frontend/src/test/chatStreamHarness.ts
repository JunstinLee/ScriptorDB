import { vi, type Mock } from "vitest";

/** `useChatStream` 的入参：用例只覆盖关心的字段。 */
export interface ChatStreamHarnessParams {
  activeSessionId: string | null;
  addUserMessage: (content: string, attachments: string[], crawlUrl: string | null) => void;
  appendEvent: (sessionId: string, event: unknown) => void;
  appendAction: (event: unknown) => void;
  appendStreamingText: (delta: string) => void;
  createNewSession: () => Promise<string | null>;
  finalizeAssistantMessage: (fullOutput: string) => void;
  handleWorkspaceMissing: () => void;
  refreshSessionTitle: (sid: string) => Promise<void>;
  refreshUndo: () => Promise<void>;
  setLoading: (loading: boolean) => void;
  selectedModel: string;
  selectedProvider: string;
  onBrowserActivity: () => void;
  setBrowserActive: (v: boolean) => void;
  setActiveMainTab: (v: "chat" | "browser") => void;
  hasRunState: (sessionId: string, runId: string) => boolean;
  resetRun: (sessionId: string, runId: string) => void;
}

export interface ApprovalRequestLike {
  type: "approval_request";
  run_id: string;
  request_id: string;
  calls: Array<{ tool_call_id: string; tool_name: string; args: Record<string, unknown> }>;
}

export interface CompleteTakeoverCallbacks {
  readonly onError: (error: Error) => void;
  readonly onDone: () => void;
}

export function makeChatParams(
  overrides: Partial<ChatStreamHarnessParams> = {},
): ChatStreamHarnessParams {
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
    hasRunState: vi.fn(() => false),
    resetRun: vi.fn(),
    ...overrides,
  };
}

/** 捕获 `completeTakeover` 传入的 onDone/onError，供用例手动触发终态。 */
export function captureCompleteTakeover(
  completeTakeover: Mock,
): CompleteTakeoverCallbacks {
  let callbacks: { onDone: () => void; onError: (e: Error) => void } | null = null;
  completeTakeover.mockImplementation(
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

/** 捕获 `streamChat` 传入的 onApprovalRequest，供用例注入审批请求事件。 */
export function captureApprovalRequest(
  streamChat: Mock,
): { setApprovalRequest: (e: ApprovalRequestLike) => void } {
  let approvalCb: ((e: ApprovalRequestLike) => void) | null = null;
  streamChat.mockImplementation(
    (
      _sid: string,
      _body: unknown,
      callbacks: { onApprovalRequest?: (e: ApprovalRequestLike) => void },
    ) => {
      approvalCb = callbacks.onApprovalRequest ?? null;
      return new AbortController();
    },
  );
  return {
    setApprovalRequest: (e: ApprovalRequestLike) => approvalCb!(e),
  };
}
