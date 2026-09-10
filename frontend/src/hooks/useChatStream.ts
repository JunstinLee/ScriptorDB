import { useCallback, useEffect, useRef, useState } from "react";
import {
  attachSessionStream,
  fetchActiveRun,
  streamChat,
  submitApproval,
  WorkspaceNotSelectedError,
  type SseStreamCallbacks,
} from "../api/client";
import { completeTakeover as completeTakeoverApi, cancelTakeover as cancelTakeoverApi } from "../api/browser";
import { useTakeoverState } from "./useTakeoverState";
import type {
  ApprovalRequestEvent,
  BrowserActionEvent,
  FilterSchema,
  LoginFlowStatus,
  LoginFormPayload,
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
  /** 本地是否已按 run_id 累积过状态：决定重挂用增量游标还是 from_index=0 重建 */
  hasRunState: (sessionId: string, runId: string) => boolean;
  /** 按 run_id 清空本地累积（重建前调用，避免重放时二次追加） */
  resetRun: (sessionId: string, runId: string) => void;
}

/** 断连重挂的最大尝试次数与基础退避 */
const MAX_REATTACH_ATTEMPTS = 5;
const REATTACH_BASE_MS = 500;
const REATTACH_MAX_MS = 5000;

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
    hasRunState,
    resetRun,
  } = params;

  const abortRef = useRef<AbortController | null>(null);
  const takeoverAbortRef = useRef<AbortController | null>(null);
  const approvalSessionIdRef = useRef<string | null>(null);
  // 最近收到的 SSE 事件序号（`id:` 行）：增量重挂的游标
  const lastEventIdRef = useRef(0);
  const reattachAttemptsRef = useRef(0);
  // 已附加的 "session:run"：避免挂载 effect 重复重挂同一 run
  const attachedRunRef = useRef("");
  const [approvalRequest, setApprovalRequest] =
    useState<ApprovalRequestEvent | null>(null);
  // 最近一次 browser_detect_filters 的 Filter Schema（新 run 开始时清空）
  const [filterSchema, setFilterSchema] = useState<FilterSchema | null>(null);
  // 最近一次自动检测到的登录表单（login_form_detected / human_takeover_request 携带）
  const [loginFormInfo, setLoginFormInfo] = useState<LoginFormPayload | null>(null);
  // 最近一次 autofill 登录流程状态（login_flow_status 携带；非敏感）
  const [loginFlowStatus, setLoginFlowStatus] = useState<LoginFlowStatus | null>(null);
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
        if (event.type === "error") {
          // 把错误提示写进 assistant 消息气泡（如站点不可用中止的英文提示），
          // 而不只是 run 卡片的错误横幅。appendStreamingText 会附着/新建
          // assistant 消息，跟随真实消息流落库。
          appendStreamingText(`\n\n${event.message}`);
        }
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
          // 新 run 开始时清空旧 schema/登录表单/登录流程状态，避免残留误导面板/抽屉
          setFilterSchema(null);
          setLoginFormInfo(null);
          setLoginFlowStatus(null);
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
          if (event.login_form) setLoginFormInfo(event.login_form);
          takeover.enterWaiting(
            event.reason,
            event.trigger || "",
            event.run_id,
          );
          setBrowserActive(true);
          setActiveMainTab("browser");
        }
        if (event.type === "login_form_detected") {
          setLoginFormInfo(event.login_form);
        }
        if (event.type === "login_flow_status") {
          setLoginFlowStatus({
            site: event.site,
            login_form_detected: event.login_form_detected,
            configured: event.configured,
            username_filled: event.username_filled,
            password_filled: event.password_filled,
            extra_required: event.extra_required,
            extra_filled: event.extra_filled,
            needs_otp: event.needs_otp,
            manual_otp_guided: event.manual_otp_guided,
            fill_ok: event.fill_ok,
            fill_error: event.fill_error,
          });
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
      // 终态：清理重挂状态
      reattachAttemptsRef.current = 0;
      attachedRunRef.current = "";
      lastEventIdRef.current = 0;
      finalizeAssistantMessage(fullOutput);
      setLoading(false);
      void refreshSessionTitle(sid);
      void refreshUndo();
    },
    [finalizeAssistantMessage, refreshSessionTitle, refreshUndo, setLoading],
  );

  const markAttached = useCallback((sid: string, runId: string) => {
    attachedRunRef.current = `${sid}:${runId}`;
  }, []);

  // 重挂与退避重挂互相调用：用 ref 打破 useCallback 循环依赖
  const reattachRef = useRef<(sid: string, requireSuspended: boolean) => Promise<void>>(
    async () => {},
  );
  const scheduleReattachRef = useRef<(sid: string) => void>(() => {});

  const attachCallbacks = useCallback(
    (sid: string): SseStreamCallbacks => ({
      onEvent: makeEventCallback(sid),
      onError: makeErrorCallback(),
      onDone: makeDoneCallback(sid),
      onDetached: (lastEventId) => {
        lastEventIdRef.current = lastEventId;
        scheduleReattachRef.current(sid);
      },
      onApprovalRequest: (event) => setApprovalRequest(event),
    }),
    [makeEventCallback, makeErrorCallback, makeDoneCallback],
  );

  /** 按本地状态选择重放起点：已有该 run 状态 → 增量；否则清空重建。 */
  const openRunStream = useCallback(
    (sid: string, runId: string) => {
      const incremental = hasRunState(sid, runId);
      const fromIndex = incremental ? lastEventIdRef.current : 0;
      if (!incremental) {
        resetRun(sid, runId);
        lastEventIdRef.current = 0;
      }
      console.log(
        "[useChatStream] reattach sid=%s run_id=%s from_index=%d",
        sid,
        runId,
        fromIndex,
      );
      approvalSessionIdRef.current = sid;
      markAttached(sid, runId);
      abortRef.current = attachSessionStream(sid, fromIndex, attachCallbacks(sid));
    },
    [hasRunState, resetRun, markAttached, attachCallbacks],
  );

  // 断连后有限次退避重挂：从 /active-run 取回 run_id 再按本地状态选游标
  const scheduleReattach = useCallback(
    (sid: string) => {
      if (reattachAttemptsRef.current >= MAX_REATTACH_ATTEMPTS) {
        console.warn("[useChatStream] reattach giving up sid=%s", sid);
        setLoading(false);
        return;
      }
      const attempt = reattachAttemptsRef.current++;
      const delay = Math.min(REATTACH_BASE_MS * 2 ** attempt, REATTACH_MAX_MS);
      console.log(
        "[useChatStream] detached sid=%s last_id=%d retry_in=%dms attempt=%d",
        sid,
        lastEventIdRef.current,
        delay,
        attempt + 1,
      );
      setTimeout(() => {
        void reattachRef.current(sid, false);
      }, delay);
    },
    [setLoading],
  );

  /** 取回活动 run 并重挂；requireSuspended=true 时仅在挂起态重挂（页面挂载用）。 */
  const reattach = useCallback(
    async (sid: string, requireSuspended: boolean) => {
      let info;
      try {
        info = await fetchActiveRun(sid);
      } catch (err) {
        console.warn("[useChatStream] reattach: active-run failed sid=%s", sid, err);
        return;
      }
      if (!info.run_id) return;
      if (requireSuspended && info.suspended === null) return;
      if (attachedRunRef.current === `${sid}:${info.run_id}`) return;
      setLoading(true);
      openRunStream(sid, info.run_id);
    },
    [openRunStream, setLoading],
  );

  useEffect(() => {
    reattachRef.current = reattach;
    scheduleReattachRef.current = scheduleReattach;
  }, [reattach, scheduleReattach]);

  // 页面挂载 / 会话切换：重放挂起态事件（human_takeover_request / approval_request），
  // 既有抽屉与确认框由重放事件自行恢复
  useEffect(() => {
    if (!activeSessionId) return;
    void reattachRef.current(activeSessionId, true);
  }, [activeSessionId]);

  const handleSend = useCallback(
    (prompt: string, attachments: string[], crawlUrl: string | null) => {
      const sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt, attachments, crawlUrl);
        setLoading(true);
        approvalSessionIdRef.current = sid;
        // 新 run：重置重挂状态
        reattachAttemptsRef.current = 0;
        attachedRunRef.current = "";
        lastEventIdRef.current = 0;

        abortRef.current = streamChat(
          sid,
          {
            prompt,
            attachments,
            model: selectedModel || null,
            provider: selectedProvider || null,
            crawl_url: crawlUrl,
          },
          attachCallbacks(sid),
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
      attachCallbacks,
      createNewSession,
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
    loginFormInfo,
    loginFlowStatus,
    takeoverInfo: takeover.info,
    handleTakeoverComplete,
    handleTakeoverCancel,
    handleEnterHumanControl,
  };
}
