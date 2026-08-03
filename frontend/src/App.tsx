import { useCallback, useEffect, useRef, useState } from "react";
import { Toast } from "@heroui/react";
import ChatPanel from "./components/ChatPanel";
import ConfirmDialog from "./components/common/ConfirmDialog";
import MainTabBar from "./components/MainTabBar";
import SchemaSidebar from "./components/SchemaSidebar";
import SettingsModal from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";
import SwitchingOverlay from "./components/common/SwitchingOverlay";
import WorkspacePicker from "./components/WorkspacePicker";
import { BrowserWorkspace } from "./components/BrowserWorkspace";
import { useAppSettings } from "./hooks/useAppSettings";
import { useBrowser } from "./hooks/useBrowser";
import { useBrowserActions } from "./hooks/useBrowser";
import { useProfiles } from "./hooks/useBrowser";
import { useCookies } from "./hooks/useBrowser";
import { useChatStream } from "./hooks/useChatStream";
import { useSchema } from "./hooks/useSchema";
import { useSessions } from "./hooks/useSessions";
import { useRuns } from "./hooks/useRuns";
import { useUndo } from "./hooks/useUndo";
import { useWorkspaces } from "./hooks/useWorkspaces";
import { fetchSettings } from "./api/settings";
import {
  saveProfile,
  loadProfile,
  deleteProfile,
  updateProfile,
  deleteCookie,
  clearAllCookies,
  showTakeoverWindow,
} from "./api/browser";
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
  const { actions: browserActions, appendAction, clearActions } = useBrowserActions();
  const { profiles, loading: profilesLoading, refresh: refreshProfiles } = useProfiles(workspace?.id ?? null);
  const { cookies, loading: cookiesLoading, refresh: refreshCookies } = useCookies(workspace?.id ?? null, browserState?.launched ?? false);

  const onBrowserActivity = useCallback(() => {
    setBrowserActive(true);
    setBrowserEnabled(true);
    setActiveMainTab("browser");
  }, []);

  const handleWorkspaceMissing = useCallback(() => {
    clearRuns();
    setPickerOpen(true);
  }, [clearRuns]);

  const { handleSend, handleApprovalSubmit, approvalRequest, takeoverInfo, handleTakeoverComplete, handleTakeoverCancel, handleEnterHumanControl } = useChatStream({
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
  });

  const handleNewSession = useCallback(() => {
    setBrowserActive(false);
    setActiveMainTab("chat");
    clearActions();
    void createNewSession();
  }, [createNewSession, clearActions]);

  const handleSwitchSession = useCallback(
    (id: string) => {
      setBrowserActive(false);
      setActiveMainTab("chat");
      clearActions();
      switchSession(id);
    },
    [switchSession, clearActions],
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
    if (!workspace?.id) return;
    fetchSettings().then((s) => setBrowserEnabled(s.browser_enabled)).catch((e) => { console.error("fetchSettings failed:", e); });
  }, [settingsChanged, workspace?.id]);

  const handleOpenWorkspacePicker = useCallback(() => {
    setPickerOpen(true);
  }, []);

  const handleSaveProfile = useCallback(async (name: string) => {
    await saveProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleLoadProfile = useCallback(async (name: string) => {
    await loadProfile(name);
    refreshCookies();
  }, [refreshCookies]);

  const handleDeleteProfile = useCallback(async (name: string) => {
    await deleteProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleUpdateProfile = useCallback(async (name: string) => {
    await updateProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleDeleteCookie = useCallback(async (name: string) => {
    await deleteCookie(name);
    refreshCookies();
  }, [refreshCookies]);

  const handleClearCookies = useCallback(async () => {
    await clearAllCookies();
    refreshCookies();
  }, [refreshCookies]);

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
        onSwitchSession={handleSwitchSession}
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
          <MainTabBar
            activeMainTab={activeMainTab}
            onTabChange={setActiveMainTab}
            browserLoading={browserLoading}
          />
        )}

        <div className="flex flex-1 min-h-0 min-w-0">
          {activeMainTab === "browser" ? (
            <BrowserWorkspace
              state={browserState}
              loading={browserLoading}
              error={browserError}
              actions={browserActions}
              isRunning={isLoading}
              takeoverInfo={takeoverInfo}
              onTakeoverComplete={(result) => {
                if (activeSessionId) {
                  handleTakeoverComplete(activeSessionId, result);
                }
              }}
              onTakeoverCancel={() => {
                if (activeSessionId) {
                  handleTakeoverCancel(activeSessionId, takeoverInfo.runId);
                }
              }}
              onEnterHumanControl={() => {
                if (activeSessionId) {
                  handleEnterHumanControl(activeSessionId);
                }
              }}
              onShowTakeoverWindow={() => showTakeoverWindow()}
              onClearActions={clearActions}
              profiles={profiles}
              cookies={cookies}
              cookiesLoading={cookiesLoading}
              onLoadProfile={handleLoadProfile}
              sessionId={activeSessionId ?? ""}
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
        browserEnabled={browserEnabled}
        onViewBrowser={() => setActiveMainTab("browser")}
        profiles={profiles}
        profilesLoading={profilesLoading}
        cookies={cookies}
        cookiesLoading={cookiesLoading}
        onSaveProfile={handleSaveProfile}
        onLoadProfile={handleLoadProfile}
        onDeleteProfile={handleDeleteProfile}
        onUpdateProfile={handleUpdateProfile}
        onDeleteCookie={handleDeleteCookie}
        onClearCookies={handleClearCookies}
        onRefreshCookies={refreshCookies}
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

      {switchingWorkspace && <SwitchingOverlay />}
    </div>
  );
}
