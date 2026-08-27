import { useCallback, useRef, useState } from "react";
import {
  streamChat,
  submitApproval,
  WorkspaceNotSelectedError,
} from "../api/client";
import { completeTakeover as completeTakeoverApi, cancelTakeover as cancelTakeoverApi } from "../api/browser";
import { useTakeoverState } from "./useTakeoverState";
import type {
  ApprovalRequestEvent,
  BrowserActionEvent,
  FilterSchema,
  StreamRunEvent,
} from "../types";

interface UseChatStreamParams {
  activeSessionId: string | null;
  addUserMessage: (content: string, attachments: string[], crawlUrl: string | null) => void;
  appendEvent: (sessionId: string, event: StreamRunEvent) => void;
  appendAction: (event: BrowserActionEvent) => void;
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
}

export function useChatStream(params: UseChatStreamParams) {
  const {
    activeSessionId,
    addUserMessage,
    appendEvent,
    appendAction,
    appendStreamingText,
    createNewSession,
    finalizeAssistantMessage,
    handleWorkspaceMissing,
    refreshSessionTitle,
    refreshUndo,
    setLoading,
    selectedModel,
    selectedProvider,
    onBrowserActivity,
    setBrowserActive,
    setActiveMainTab,
  } = params;

  const abortRef = useRef<AbortController | null>(null);
  const takeoverAbortRef = useRef<AbortController | null>(null);
  const approvalSessionIdRef = useRef<string | null>(null);
  const [approvalRequest, setApprovalRequest] =
    useState<ApprovalRequestEvent | null>(null);
  // 最近一次 browser_detect_filters 的 Filter Schema（新 run 开始时清空）
  const [filterSchema, setFilterSchema] = useState<FilterSchema | null>(null);
  const takeover = useTakeoverState(() => {
    const sid = approvalSessionIdRef.current;
    if (sid) {
      cancelTakeoverApi(sid).catch(() => {});
    }
  });

  const makeEventCallback = useCallback(
    (sid: string) =>
      (event: StreamRunEvent) => {
        appendEvent(sid, event);
        if (event.type === "text_delta") {
          appendStreamingText(event.delta);
        }
        if (
          event.type === "tool_call" &&
          event.tool_name?.startsWith("browser_")
        ) {
          onBrowserActivity();
        }
        if (event.type === "browser_action") {
          appendAction(event);
          setBrowserActive(true);
        }
        if (event.type === "run_start") {
          // 新 run 开始时清空旧 schema，避免残留误导面板/抽屉
          setFilterSchema(null);
        }
        if (
          event.type === "tool_result" &&
          event.tool_name === "browser_detect_filters"
        ) {
          try {
            const parsed = event.output
              ? (JSON.parse(event.output) as FilterSchema)
              : null;
            if (parsed && Array.isArray(parsed.filters)) {
              setFilterSchema(parsed);
            }
          } catch {
            // 忽略无法解析的 tool_result，保持现有 schema 不变
          }
        }
        if (event.type === "human_takeover_request") {
          takeover.enterWaiting(
            event.reason,
            event.trigger || "",
            event.run_id,
          );
          setBrowserActive(true);
          setActiveMainTab("browser");
        }
        if (event.type === "takeover_state_change") {
          switch (event.state) {
            case "waiting_human":
              takeover.enterWaiting(event.reason, event.trigger, event.run_id);
              break;
            case "human_control":
              takeover.enterHumanControl();
              break;
            case "resuming":
              takeover.enterResuming();
              break;
            case "cancelled":
              takeover.reset();
              break;
          }
        }
        if (event.type === "takeover_cancelled") {
          takeover.reset();
        }
      },
    [
      appendEvent,
      appendAction,
      appendStreamingText,
        onBrowserActivity,
        setBrowserActive,
        setActiveMainTab,
        takeover,
    ],
  );

  const makeErrorCallback = useCallback(
    () => (error: Error) => {
      if (error instanceof WorkspaceNotSelectedError) {
        handleWorkspaceMissing();
        return;
      }
      appendStreamingText(`\n\nError: ${error.message}`);
      setLoading(false);
      setApprovalRequest(null);
    },
    [appendStreamingText, handleWorkspaceMissing, setLoading],
  );

  const makeDoneCallback = useCallback(
    (sid: string) => (fullOutput: string) => {
      console.log(
        "[useChatStream] onDone sid=%s output_len=%s",
        sid,
        fullOutput.length,
      );
      finalizeAssistantMessage(fullOutput);
      setLoading(false);
      void refreshSessionTitle(sid);
      void refreshUndo();
    },
    [finalizeAssistantMessage, refreshSessionTitle, refreshUndo, setLoading],
  );

  const handleSend = useCallback(
    (prompt: string, attachments: string[], crawlUrl: string | null) => {
      const sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt, attachments, crawlUrl);
        setLoading(true);
        approvalSessionIdRef.current = sid;

        abortRef.current = streamChat(
          sid,
          {
            prompt,
            attachments,
            model: selectedModel || null,
            provider: selectedProvider || null,
            crawl_url: crawlUrl,
          },
          makeEventCallback(sid),
          makeErrorCallback(),
          makeDoneCallback(sid),
          (event) => {
            setApprovalRequest(event);
          },
        );
      };

      if (!sessionId) {
        void (async () => {
          const sid = await createNewSession();
          if (sid) {
            sendToSession(sid);
          }
        })();
      } else {
        sendToSession(sessionId);
      }
    },
    [
      activeSessionId,
      addUserMessage,
      createNewSession,
      makeEventCallback,
      makeErrorCallback,
      makeDoneCallback,
      selectedModel,
      selectedProvider,
      setLoading,
    ],
  );

  const handleApprovalSubmit = useCallback(
    async (
      approved: boolean,
      overrideArgs?: Record<string, Record<string, unknown>>,
    ) => {
      const request = approvalRequest;
      const sid = approvalSessionIdRef.current;
      setApprovalRequest(null);
      if (!request || !sid) return;

      // 批准/拒绝统一走短信号请求（与 /takeover/complete 同模式）：
      // 只唤醒挂起的 run，工具结果、run_end 等后续事件继续由原 chat SSE 流
      // 推送，前端不再本地合成终态事件，避免工具调用永久停留在 running。
      const approvedMap: Record<string, boolean> = {};
      for (const call of request.calls) {
        approvedMap[call.tool_call_id] = approved;
      }

      try {
        await submitApproval(sid, request.request_id, approvedMap, overrideArgs);
      } catch (error) {
        makeErrorCallback()(
          error instanceof Error ? error : new Error("Unknown error"),
        );
      }
    },
    [approvalRequest, makeErrorCallback],
  );

  const handleTakeoverComplete = useCallback(
    async (sessionId: string, result: string) => {
      // 不 abort 原 chat SSE 流：恢复是唤醒同一 run，后续事件继续由原流推送。
      takeoverAbortRef.current?.abort();
      takeover.enterResuming();

      takeoverAbortRef.current = completeTakeoverApi(
        sessionId,
        result,
        () => {
          // 唤醒成功；run 继续，最终由原流的 onDone 完成消息落库。
          takeover.reset();
        },
        (error: Error) => {
          if (error instanceof WorkspaceNotSelectedError) {
            handleWorkspaceMissing();
          } else {
            appendStreamingText(`\n\nError: ${error.message}`);
            setLoading(false);
          }
          takeover.reset();
        },
      );
    },
    [
      takeover,
      setLoading,
      handleWorkspaceMissing,
      appendStreamingText,
    ],
  );

  const handleTakeoverCancel = useCallback(
    async (sessionId: string, runId: string) => {
      abortRef.current?.abort();
      takeoverAbortRef.current?.abort();
      takeover.reset();
      await cancelTakeoverApi(sessionId, runId).catch(() => {});
      setLoading(false);
    },
    [takeover, setLoading],
  );

  const handleEnterHumanControl = useCallback(
    async (sessionId: string) => {
      const { enterHumanControl } = await import("../api/browser");
      await enterHumanControl(sessionId);
      takeover.enterHumanControl();
    },
    [takeover],
  );

  return {
    handleSend,
    handleApprovalSubmit,
    approvalRequest,
    filterSchema,
    takeoverInfo: takeover.info,
    handleTakeoverComplete,
    handleTakeoverCancel,
    handleEnterHumanControl,
  };
}
