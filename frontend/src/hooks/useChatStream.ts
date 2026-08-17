import { useCallback, useRef, useState } from "react";
import {
  streamApproval,
  streamChat,
  WorkspaceNotSelectedError,
} from "../api/client";
import { completeTakeover as completeTakeoverApi, cancelTakeover as cancelTakeoverApi } from "../api/browser";
import { useTakeoverState } from "./useTakeoverState";
import type {
  ApprovalRequestEvent,
  BrowserActionEvent,
  StreamRunEvent,
  ToolResultRunEvent,
  RunEndEvent,
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
          setActiveMainTab("browser");
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
    (approved: boolean) => {
      const request = approvalRequest;
      const sid = approvalSessionIdRef.current;
      setApprovalRequest(null);
      if (!request || !sid) return;

      if (!approved) {
        console.log(
          "[useChatStream] handleApprovalSubmit denied: run_id=%s calls=%s",
          request.run_id,
          request.calls.map((c) => c.tool_call_id).join(","),
        );
        for (const call of request.calls) {
          const event: ToolResultRunEvent = {
            type: "tool_result",
            run_id: request.run_id,
            call_id: call.tool_call_id,
            tool_name: call.tool_name,
            success: false,
            output: "User cancelled the operation",
            timestamp: new Date().toISOString(),
          };
          appendEvent(sid, event);
        }
        const runEndEvent: RunEndEvent = {
          type: "run_end",
          run_id: request.run_id,
          timestamp: new Date().toISOString(),
        };
        appendEvent(sid, runEndEvent);
        setLoading(false);
        return;
      }

      const approvedMap: Record<string, boolean> = {};
      for (const call of request.calls) {
        approvedMap[call.tool_call_id] = approved;
      }

      abortRef.current = streamApproval(
        sid,
        request.request_id,
        approvedMap,
        makeEventCallback(sid),
        makeErrorCallback(),
        makeDoneCallback(sid),
        (event) => {
          setApprovalRequest(event);
        },
      );
    },
    [
      approvalRequest,
      appendEvent,
      makeEventCallback,
      makeErrorCallback,
      makeDoneCallback,
      setLoading,
    ],
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
    takeoverInfo: takeover.info,
    handleTakeoverComplete,
    handleTakeoverCancel,
    handleEnterHumanControl,
  };
}
