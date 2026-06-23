import { useCallback, useMemo, useRef, useState } from "react";
import ChatHeader from "./components/ChatHeader";
import ChatPanel from "./components/ChatPanel";
import SchemaSidebar from "./components/SchemaSidebar";
import SettingsModal from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";
import WorkspacePicker from "./components/WorkspacePicker";
import { useAppSettings } from "./hooks/useAppSettings";
import { useSchema } from "./hooks/useSchema";
import { useSessions } from "./hooks/useSessions";
import { useRuns } from "./hooks/useRuns";
import { useWorkspaces } from "./hooks/useWorkspaces";
import {
  deleteWorkspace as apiDeleteWorkspace,
  streamChat,
  updateWorkspace as apiUpdateWorkspace,
  WorkspaceNotSelectedError,
} from "./api/client";
import { useOverlayState } from "@heroui/react";
import type {
  Run,
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

  if (!activeWorkspace) {
    return (
      <WorkspacePicker
        workspaces={workspaces}
        activeWorkspace={activeWorkspace}
        error={workspacesError}
        onActivate={handlePickerActivate}
        onCreate={handlePickerCreate}
        onRename={handlePickerRename}
        onDelete={handlePickerDelete}
        onRefresh={refreshWorkspaces}
        onCancelActive={() => {
          /* no active workspace to clear */
        }}
      />
    );
  }

  return (
    <MainApp
      workspace={activeWorkspace}
      workspaces={workspaces}
      switchingWorkspace={switchingWorkspace}
      onSwitchWorkspace={handlePickerActivate}
      onPickerCreate={handlePickerCreate}
      onWorkspaceChanged={refreshWorkspaces}
    />
  );
}

interface MainAppProps {
  workspace: WorkspaceDetail;
  workspaces: WorkspaceItem[];
  switchingWorkspace: boolean;
  onSwitchWorkspace: (id: string) => Promise<WorkspaceDetail>;
  onPickerCreate: (body: WorkspaceCreateRequest) => Promise<WorkspaceDetail>;
  onWorkspaceChanged: () => Promise<void>;
}

function MainApp({
  workspace,
  workspaces,
  switchingWorkspace,
  onSwitchWorkspace,
  onPickerCreate,
  onWorkspaceChanged,
}: MainAppProps) {
  const { getRuns, appendEvent, setRuns, clearRuns } = useRuns();
  const [pickerOpen, setPickerOpen] = useState(false);

  const handleRunsLoaded = useCallback(
    (_sessionId: string, loadedRuns: Run[]) => {
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
    refreshSessions,
  } = useSessions(handleRunsLoaded, workspace.id);

  const runs = activeSessionId ? getRuns(activeSessionId) : [];

  const { tables, loading: schemaLoading } = useSchema(workspace.id);
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
  const [highlightedRunId, setHighlightedRunId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeSessionTitle = useMemo(
    () => sessions.find((s) => s.session_id === activeSessionId)?.title ?? null,
    [sessions, activeSessionId],
  );

  const handleNewSession = useCallback(() => {
    void createNewSession();
  }, [createNewSession]);

  const handleWorkspaceMissing = useCallback(() => {
    clearRuns();
    setPickerOpen(true);
  }, [clearRuns]);

  const handleSend = useCallback(
    (prompt: string) => {
      const sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt);
        setLoading(true);

        abortRef.current = streamChat(
          sid,
          { prompt, model: selectedModel || null, provider: selectedProvider || null },
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
      setLoading,
      selectedModel,
      selectedProvider,
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

  const handleOpenWorkspacePicker = useCallback(() => {
    setPickerOpen(true);
  }, []);

  const handleCloseWorkspacePicker = useCallback(() => {
    setPickerOpen(false);
  }, []);

  const handleSwitchWorkspace = useCallback(
    async (id: string): Promise<WorkspaceDetail> => {
      const detail = await onSwitchWorkspace(id);
      await onWorkspaceChanged();
      clearRuns();
      return detail;
    },
    [clearRuns, onSwitchWorkspace, onWorkspaceChanged],
  );

  if (pickerOpen) {
    return (
      <WorkspacePicker
        workspaces={workspaces}
        activeWorkspace={workspace}
        error={null}
        onActivate={handleSwitchWorkspace}
        onCreate={async (body) => {
          const detail = await onPickerCreate(body);
          setPickerOpen(false);
          await onWorkspaceChanged();
          return detail;
        }}
        onRename={async (id, body) => {
          const detail = await apiUpdateWorkspace(id, body);
          await onWorkspaceChanged();
          return detail;
        }}
        onDelete={async (id, deleteFiles) => {
          await apiDeleteWorkspace(id, deleteFiles);
          await onWorkspaceChanged();
        }}
        onRefresh={onWorkspaceChanged}
        onCancelActive={handleCloseWorkspacePicker}
      />
    );
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        showSessionIdHover={showSessionIdHover}
        onNewSession={handleNewSession}
        onSwitchSession={switchSession}
        onDeleteSession={handleDeleteSession}
        onOpenSettings={handleOpenSettings}
        activeWorkspace={workspace}
        onOpenWorkspacePicker={handleOpenWorkspacePicker}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <ChatHeader
          activeSessionId={activeSessionId}
          activeSessionTitle={activeSessionTitle}
          showSessionIdHover={showSessionIdHover}
          settingsChanged={settingsChanged}
          onSelectionChange={(model, provider) => {
            setSelectedModel(model);
            setSelectedProvider(provider);
          }}
          activeWorkspace={workspace}
          workspaces={workspaces}
          switchingWorkspace={switchingWorkspace}
          onSwitchWorkspace={handleSwitchWorkspace}
          onRequestNewWorkspace={handleOpenWorkspacePicker}
          onOpenWorkspaceSettings={() => settingsModal.open()}
        />

        <div className="flex flex-1 flex-col min-h-0 relative">
          <ChatPanel
            activeSessionId={activeSessionId}
            messages={messages}
            runs={runs}
            isLoading={isLoading}
            onSend={handleSend}
            onNewSession={handleNewSession}
            onHighlightRun={handleHighlightRun}
          />
        </div>
      </div>

      <SchemaSidebar
        tables={tables}
        schemaLoading={schemaLoading}
        runs={runs}
        activeSessionId={activeSessionId}
        highlightedRunId={highlightedRunId}
        showSchemaSql={showSchemaSql}
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
        onSessionsChanged={() => void refreshSessions()}
        showSessionIdHover={showSessionIdHover}
        setShowSessionIdHover={setShowSessionIdHover}
        showSchemaSql={showSchemaSql}
        setShowSchemaSql={setShowSchemaSql}
        activeWorkspace={workspace}
        workspacesCount={workspaces.length}
        onWorkspaceChanged={onWorkspaceChanged}
        onOpenWorkspacePicker={handleOpenWorkspacePicker}
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
