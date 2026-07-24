import { useCallback, useEffect, useRef, useState } from "react";
import { Toast } from "@heroui/react";
import { Monitor, MessageSquare } from "lucide-react";
import ChatPanel from "./components/ChatPanel";
import ConfirmDialog from "./components/common/ConfirmDialog";
import SchemaSidebar from "./components/SchemaSidebar";
import SettingsModal from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";
import WorkspacePicker from "./components/WorkspacePicker";
import { BrowserWorkspace } from "./components/BrowserWorkspace";
import { useAppSettings } from "./hooks/useAppSettings";
import { useBrowser } from "./hooks/useBrowser";
import { useSchema } from "./hooks/useSchema";
import { useSessions } from "./hooks/useSessions";
import { useRuns } from "./hooks/useRuns";
import { useUndo } from "./hooks/useUndo";
import { useWorkspaces } from "./hooks/useWorkspaces";
import {
  streamApproval,
  streamChat,
  WorkspaceNotSelectedError,
} from "./api/client";
import { fetchSettings } from "./api/settings";
import { useOverlayState } from "@heroui/react";
import type {
  ApprovalRequestEvent,
  Run,
  RunEndEvent,
  StreamRunEvent,
  ToolResultRunEvent,
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "./types";

export default function App() {
  const {
    workspaces,
    activeWorkspace,
    isLoading: workspacesLoading,
    error: workspacesError,
    refresh: refreshWorkspaces,
    createAndActivate,
    switchWorkspace,
    renameWorkspace,
    removeWorkspace,
  } = useWorkspaces();

  const [switchingWorkspace, setSwitchingWorkspace] = useState(false);

  const handlePickerActivate = useCallback(
    async (id: string): Promise<WorkspaceDetail> => {
      setSwitchingWorkspace(true);
      try {
        return await switchWorkspace(id);
      } finally {
        setSwitchingWorkspace(false);
      }
    },
    [switchWorkspace],
  );

  const handlePickerCreate = useCallback(
    async (body: WorkspaceCreateRequest): Promise<WorkspaceDetail> => {
      setSwitchingWorkspace(true);
      try {
        return await createAndActivate(body);
      } finally {
        setSwitchingWorkspace(false);
      }
    },
    [createAndActivate],
  );

  const handlePickerRename = useCallback(
    async (
      id: string,
      body: WorkspaceUpdateRequest,
    ): Promise<WorkspaceDetail> => {
      return await renameWorkspace(id, body);
    },
    [renameWorkspace],
  );

  const handlePickerDelete = useCallback(
    async (id: string, deleteFiles?: boolean): Promise<void> => {
      await removeWorkspace(id, deleteFiles);
      await refreshWorkspaces();
    },
    [removeWorkspace, refreshWorkspaces],
  );

  if (workspacesLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted">
        <span className="text-sm">Loading workspaces…</span>
      </div>
    );
  }

  return (
    <MainApp
      workspace={activeWorkspace}
      workspaces={workspaces}
      workspacesError={workspacesError}
      switchingWorkspace={switchingWorkspace}
      onSwitchWorkspace={handlePickerActivate}
      onCreateWorkspace={handlePickerCreate}
      onRenameWorkspace={handlePickerRename}
      onDeleteWorkspace={handlePickerDelete}
      onRefreshWorkspaces={refreshWorkspaces}
    />
  );
}

interface MainAppProps {
  workspace: WorkspaceDetail | null;
  workspaces: WorkspaceItem[];
  workspacesError: string | null;
  switchingWorkspace: boolean;
  onSwitchWorkspace: (id: string) => Promise<WorkspaceDetail>;
  onCreateWorkspace: (body: WorkspaceCreateRequest) => Promise<WorkspaceDetail>;
  onRenameWorkspace: (id: string, body: WorkspaceUpdateRequest) => Promise<WorkspaceDetail>;
  onDeleteWorkspace: (id: string, deleteFiles?: boolean) => Promise<void>;
  onRefreshWorkspaces: () => Promise<void>;
}

function MainApp({
  workspace,
  workspaces,
  workspacesError,
  switchingWorkspace,
  onSwitchWorkspace,
  onCreateWorkspace,
  onRenameWorkspace,
  onDeleteWorkspace,
  onRefreshWorkspaces,
}: MainAppProps) {
  const { getRuns, appendEvent, setRuns, clearRuns } = useRuns();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [undoConfirmGroupId, setUndoConfirmGroupId] = useState<number | null>(null);
  const [approvalRequest, setApprovalRequest] = useState<ApprovalRequestEvent | null>(null);
  const approvalSessionIdRef = useRef<string | null>(null);

  const handleRunsLoaded = useCallback(
    (_sessionId: string, loadedRuns: Run[]) => {
      console.log(
        "[App] setRuns: sessionId=%s runs=%d run_ids=%s",
        _sessionId,
        loadedRuns.length,
        loadedRuns
          .map(
            (r) =>
              r.run_id +
              "(" +
              r.status +
              "," +
              r.tool_invocations.length +
              "tools)",
          )
          .join(", "),
      );
      setRuns(_sessionId, loadedRuns);
    },
    [setRuns],
  );

  const {
    sessions,
    activeSessionId,
    messages,
    isLoading,
    createNewSession,
    removeSession,
    switchSession,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    setLoading,
    refreshSessionTitle,
    reloadActiveSession,
  } = useSessions(handleRunsLoaded, workspace?.id);

  const runs = activeSessionId ? getRuns(activeSessionId) : [];

  const { tables, loading: schemaLoading, refresh: refreshSchema } = useSchema(workspace?.id);
  const abortRef = useRef<AbortController | null>(null);
  const settingsModal = useOverlayState();
  const [settingsChanged, setSettingsChanged] = useState(0);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const {
    showSessionIdHover,
    setShowSessionIdHover,
    showSchemaSql,
    setShowSchemaSql,
  } = useAppSettings();
  const { groups: undoGroups, refresh: refreshUndo, revertAndTrim } = useUndo();
  const [highlightedRunId, setHighlightedRunId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [browserActive, setBrowserActive] = useState(false);
  const [activeMainTab, setActiveMainTab] = useState<"chat" | "browser">("chat");
  const [browserEnabled, setBrowserEnabled] = useState(false);
  const { state: browserState, loading: browserLoading, error: browserError } =
    useBrowser(browserEnabled, workspace?.id ?? null);

  const handleNewSession = useCallback(() => {
    void createNewSession();
  }, [createNewSession]);

  const handleWorkspaceMissing = useCallback(() => {
    clearRuns();
    setPickerOpen(true);
  }, [clearRuns]);

  const handleSend = useCallback(
    (prompt: string, attachments: string[], crawlUrl: string | null) => {
      const sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt, attachments, crawlUrl);
        setLoading(true);
        approvalSessionIdRef.current = sid;

        const onEvent = (event: StreamRunEvent) => {
          appendEvent(sid, event);
          if (event.type === "text_delta") {
            appendStreamingText(event.delta);
          }
          if (event.type === "tool_call" && event.tool_name?.startsWith("browser_")) {
            setBrowserActive(true);
            setBrowserEnabled(true);
            setActiveMainTab("browser");
          }
        };

        const onError = (error: Error) => {
          if (error instanceof WorkspaceNotSelectedError) {
            handleWorkspaceMissing();
            return;
          }
          appendStreamingText(`\n\nError: ${error.message}`);
          setLoading(false);
          setApprovalRequest(null);
        };

        const onDone = (fullOutput: string) => {
          finalizeAssistantMessage(fullOutput);
          setLoading(false);
          void refreshSessionTitle(sid);
          void refreshUndo();
        };

        abortRef.current = streamChat(
          sid,
          { prompt, attachments, model: selectedModel || null, provider: selectedProvider || null, crawl_url: crawlUrl },
          onEvent,
          onError,
          onDone,
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
      appendEvent,
      appendStreamingText,
      createNewSession,
      finalizeAssistantMessage,
      handleWorkspaceMissing,
      refreshSessionTitle,
      refreshUndo,
      setLoading,
      selectedModel,
      selectedProvider,
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
          "[App] handleApprovalSubmit denied: run_id=%s calls=%s",
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
          console.log(
            "[App] handleApprovalSubmit: emitting local tool_result for call_id=%s",
            call.tool_call_id,
          );
          appendEvent(sid, event);
        }
        const runEndEvent: RunEndEvent = {
          type: "run_end",
          run_id: request.run_id,
          timestamp: new Date().toISOString(),
        };
        appendEvent(sid, runEndEvent);
        setLoading(false);
      }

      const approvedMap: Record<string, boolean> = {};
      for (const call of request.calls) {
        approvedMap[call.tool_call_id] = approved;
      }

      abortRef.current = streamApproval(
        sid,
        request.request_id,
        approvedMap,
        (event) => {
          appendEvent(sid, event);
          if (event.type === "text_delta") {
            appendStreamingText(event.delta);
          }
        },
        (error) => {
          if (error instanceof WorkspaceNotSelectedError) {
            handleWorkspaceMissing();
            return;
          }
          appendStreamingText(`\n\nError: ${error.message}`);
          setLoading(false);
        },
        (fullOutput) => {
          finalizeAssistantMessage(fullOutput);
          setLoading(false);
          void refreshSessionTitle(sid);
          void refreshUndo();
        },
        (event) => {
          setApprovalRequest(event);
        },
      );
    },
    [
      approvalRequest,
      appendEvent,
      appendStreamingText,
      finalizeAssistantMessage,
      handleWorkspaceMissing,
      refreshSessionTitle,
      refreshUndo,
      setLoading,
    ],
  );

  const handleDeleteSession = useCallback(
    (id: string) => {
      void removeSession(id);
    },
    [removeSession],
  );

  const handleOpenSettings = useCallback(() => {
    settingsModal.open();
  }, [settingsModal]);

  const handleHighlightRun = useCallback((runId: string) => {
    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current);
    }
    setHighlightedRunId(null);
    requestAnimationFrame(() => {
      setHighlightedRunId(runId);
      highlightTimeoutRef.current = setTimeout(() => {
        setHighlightedRunId(null);
      }, 5500);
    });
  }, []);

  const handleRevertToHere = useCallback((groupId: number) => {
    setUndoConfirmGroupId(groupId);
  }, []);

  const handleRevertConfirm = useCallback(async () => {
    if (undoConfirmGroupId === null) return;
    const groupId = undoConfirmGroupId;
    setUndoConfirmGroupId(null);
    try {
      await revertAndTrim(groupId);
      await refreshUndo();
      if (activeSessionId) {
        await reloadActiveSession(activeSessionId);
      }
    } catch {
      // error handled in useUndo
    }
  }, [undoConfirmGroupId, revertAndTrim, refreshUndo, activeSessionId, reloadActiveSession]);

  useEffect(() => {
    if (activeSessionId || workspace?.id) {
      void refreshUndo();
    }
  }, [activeSessionId, workspace?.id, refreshUndo]);

  useEffect(() => {
    setBrowserActive(false);
    setActiveMainTab("chat");
  }, [activeSessionId]);

  useEffect(() => {
    if (!workspace?.id) return;
    fetchSettings().then((s) => setBrowserEnabled(s.browser_enabled)).catch((e) => { console.error("fetchSettings failed:", e); });
  }, [settingsChanged, workspace?.id]);

  const handleOpenWorkspacePicker = useCallback(() => {
    setPickerOpen(true);
  }, []);

  const handleDatabaseConfigured = useCallback(async () => {
    await onRefreshWorkspaces();
    void refreshSchema();
    clearRuns();
  }, [clearRuns, onRefreshWorkspaces, refreshSchema]);

  const handleCloseWorkspacePicker = useCallback(() => {
    setPickerOpen(false);
  }, []);

  const handleSwitchWorkspace = useCallback(
    async (id: string): Promise<WorkspaceDetail> => {
      const detail = await onSwitchWorkspace(id);
      await onRefreshWorkspaces();
      clearRuns();
      return detail;
    },
    [clearRuns, onSwitchWorkspace, onRefreshWorkspaces],
  );

  const pickerClosable = !!workspace;

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Toast.Provider />
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        showSessionIdHover={showSessionIdHover}
        onNewSession={handleNewSession}
        onSwitchSession={switchSession}
        onDeleteSession={handleDeleteSession}
        onOpenSettings={handleOpenSettings}
        activeWorkspace={workspace}
        workspaces={workspaces}
        switchingWorkspace={switchingWorkspace}
        onSwitchWorkspace={handleSwitchWorkspace}
        onOpenWorkspacePicker={handleOpenWorkspacePicker}
        onRequestNewWorkspace={handleOpenWorkspacePicker}
        onDatabaseConfigured={handleDatabaseConfigured}
      />

      <div className="flex flex-1 flex-col min-w-0">
        {(browserActive || browserState?.launched) && (
          <div className="flex shrink-0 items-center border-b border-grid bg-background px-4">
            <button
              onClick={() => setActiveMainTab("chat")}
              className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                activeMainTab === "chat"
                  ? "border-accent text-accent"
                  : "border-transparent text-muted hover:text-foreground"
              }`}
            >
              <MessageSquare className="size-3.5" />
              Chat
            </button>

            <button
              onClick={() => setActiveMainTab("browser")}
              className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                activeMainTab === "browser"
                  ? "border-accent text-accent"
                  : "border-transparent text-muted hover:text-foreground"
              }`}
            >
              <Monitor className="size-3.5" />
              Browser
              {browserLoading && (
                <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
              )}
            </button>
          </div>
        )}

        <div className="flex flex-1 min-h-0 min-w-0">
          {activeMainTab === "browser" ? (
            <BrowserWorkspace
              state={browserState}
              loading={browserLoading}
              error={browserError}
            />
          ) : (
            <ChatPanel
              activeSessionId={activeSessionId}
              messages={messages}
              runs={runs}
              isLoading={isLoading}
              settingsChanged={settingsChanged}
              workspace={workspace}
              tables={tables}
              undoGroups={undoGroups}
              onSend={handleSend}
              onNewSession={handleNewSession}
              onRevertToHere={handleRevertToHere}
              onHighlightRun={handleHighlightRun}
              onSelectionChange={(model, provider) => {
                setSelectedModel(model);
                setSelectedProvider(provider);
              }}
            />
          )}
        </div>
      </div>

      <SchemaSidebar
        tables={tables}
        schemaLoading={schemaLoading}
        runs={runs}
        activeSessionId={activeSessionId}
        highlightedRunId={highlightedRunId}
        showSchemaSql={showSchemaSql}
        browserState={browserState}
        browserLoading={browserLoading}
        onViewBrowser={() => setActiveMainTab("browser")}
      />

      <SettingsModal
        isOpen={settingsModal.isOpen}
        onOpenChange={(open) => {
          if (open) settingsModal.open();
          else {
            settingsModal.close();
            setSettingsChanged((v) => v + 1);
          }
        }}
        showSessionIdHover={showSessionIdHover}
        setShowSessionIdHover={setShowSessionIdHover}
        showSchemaSql={showSchemaSql}
        setShowSchemaSql={setShowSchemaSql}
        activeWorkspace={workspace}
        workspacesCount={workspaces.length}
        onWorkspaceChanged={onRefreshWorkspaces}
        onOpenWorkspacePicker={handleOpenWorkspacePicker}
      />

      <ConfirmDialog
        isOpen={undoConfirmGroupId !== null}
        onClose={() => setUndoConfirmGroupId(null)}
        onConfirm={handleRevertConfirm}
        title="Undo to here"
        message="This action will undo all database changes made from the current turn onward and delete the current turn and all subsequent chat history."
        confirmLabel="Undo"
      />

      <ConfirmDialog
        isOpen={approvalRequest !== null}
        onClose={() => handleApprovalSubmit(false)}
        onConfirm={() => handleApprovalSubmit(true)}
        title="Confirm Import"
        message={
          approvalRequest
            ? `${approvalRequest.calls[0]?.tool_name ?? "import"} will write ${approvalRequest.calls[0]?.row_count ?? ""} row(s) into table ${approvalRequest.calls[0]?.table_name ?? ""}. Proceed?`
            : ""
        }
        confirmLabel="Confirm"
      />

      <WorkspacePicker
        workspaces={workspaces}
        activeWorkspace={workspace}
        error={workspacesError}
        onActivate={handleSwitchWorkspace}
        onCreate={async (body) => {
          const detail = await onCreateWorkspace(body);
          setPickerOpen(false);
          await onRefreshWorkspaces();
          return detail;
        }}
        onRename={async (id, body) => {
          const detail = await onRenameWorkspace(id, body);
          await onRefreshWorkspaces();
          return detail;
        }}
        onDelete={async (id, deleteFiles) => {
          await onDeleteWorkspace(id, deleteFiles);
          await onRefreshWorkspaces();
        }}
        onRefresh={onRefreshWorkspaces}
        onCancelActive={handleCloseWorkspacePicker}
        isOpen={pickerOpen || !workspace}
        onClose={handleCloseWorkspacePicker}
        isClosable={pickerClosable}
      />

      {switchingWorkspace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="rounded-lg border bg-surface px-6 py-4 shadow-lg">
            <span className="text-sm text-muted">Switching workspace…</span>
          </div>
        </div>
      )}
    </div>
  );
}
