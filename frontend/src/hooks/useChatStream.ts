import { useCallback, useRef, useState } from "react";
import {
  streamApproval,
  streamChat,
  WorkspaceNotSelectedError,
} from "../api/client";
import { completeTakeover as completeTakeoverApi } from "../api/browser";
import type {
  ApprovalRequestEvent,
  BrowserActionEvent,
  HumanTakeoverRequestEvent,
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
  setLatestBrowserAction: (action: BrowserActionEvent) => void;
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
    setLatestBrowserAction,
  } = params;

  const abortRef = useRef<AbortController | null>(null);
  const approvalSessionIdRef = useRef<string | null>(null);
  const [approvalRequest, setApprovalRequest] =
    useState<ApprovalRequestEvent | null>(null);
  const [takeoverEvent, setTakeoverEvent] =
    useState<HumanTakeoverRequestEvent | null>(null);

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
          setLatestBrowserAction(event);
          setBrowserActive(true);
          setActiveMainTab("browser");
        }
        if (event.type === "human_takeover_request") {
          setTakeoverEvent(event as HumanTakeoverRequestEvent);
          setLoading(false);
          setBrowserActive(true);
          setActiveMainTab("browser");
          return;
        }
      },
    [
      appendEvent,
      appendAction,
      appendStreamingText,
      onBrowserActivity,
      setBrowserActive,
      setActiveMainTab,
      setLatestBrowserAction,
      setLoading,
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
      abortRef.current?.abort();
      setTakeoverEvent(null);
      setLoading(true);
      await completeTakeoverApi(sessionId, result);
    },
    [setLoading],
  );

  const handleTakeoverCancel = useCallback(() => {
    abortRef.current?.abort();
    setTakeoverEvent(null);
    setLoading(false);
  }, [setLoading]);

  return {
    handleSend,
    handleApprovalSubmit,
    approvalRequest,
    takeoverEvent,
    handleTakeoverComplete,
    handleTakeoverCancel,
  };
}
