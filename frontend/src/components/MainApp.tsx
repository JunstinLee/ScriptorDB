import { useCallback, useEffect, useRef, useState } from "react";
import { Toast } from "@heroui/react";
import ChatPanel from "./ChatPanel";
import MainTabBar from "./MainTabBar";
import SchemaSidebar from "./SchemaSidebar";
import Sidebar from "./Sidebar";
import { BrowserWorkspace } from "./BrowserWorkspace";
import AppDialogs from "./AppDialogs";
import { useAppSettings } from "../hooks/useAppSettings";
import { useBrowserPanel } from "../hooks/useBrowserPanel";
import { useChatStream } from "../hooks/useChatStream";
import { useSchema } from "../hooks/useSchema";
import { useSessions } from "../hooks/useSessions";
import { useRuns } from "../hooks/useRuns";
import { useUndo } from "../hooks/useUndo";
import { closeBrowser, showTakeoverWindow } from "../api/browser";
import type {
  Run,
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "../types";

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

/**
 * 应用主壳：三栏布局（Sidebar / 主区 / SchemaSidebar）+ 会话编排。
 * 浏览器相关状态见 useBrowserPanel，弹窗见 AppDialogs。
 */
export default function MainApp({
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsChanged, setSettingsChanged] = useState(0);

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

  const browserPanel = useBrowserPanel(workspace?.id);
  const {
    browserActive,
    setBrowserActive,
    activeMainTab,
    setActiveMainTab,
    appendAction,
    clearActions,
  } = browserPanel;

  const handleWorkspaceMissing = useCallback(() => {
    clearRuns();
    setPickerOpen(true);
  }, [clearRuns]);

  const { handleSend, handleApprovalSubmit, approvalRequest, filterSchema, loginFormInfo, takeoverInfo, handleTakeoverComplete, handleTakeoverCancel, handleEnterHumanControl } = useChatStream({
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
    onBrowserActivity: browserPanel.onBrowserActivity,
    setBrowserActive,
    setActiveMainTab,
  });

  const handleNewSession = useCallback(() => {
    setBrowserActive(false);
    setActiveMainTab("chat");
    clearActions();
    void createNewSession();
  }, [createNewSession, setBrowserActive, setActiveMainTab, clearActions]);

  const handleSwitchSession = useCallback(
    (id: string) => {
      setBrowserActive(false);
      setActiveMainTab("chat");
      clearActions();
      switchSession(id);
    },
    [switchSession, setBrowserActive, setActiveMainTab, clearActions],
  );

  const handleDeleteSession = useCallback(
    (id: string) => {
      void removeSession(id);
    },
    [removeSession],
  );

  const handleOpenSettings = useCallback(() => {
    setSettingsOpen(true);
  }, []);

  /** 设置弹窗关闭：刷新模型列表/globeMode（ChatPanel）与 browser_enabled（useBrowserPanel） */
  const handleSettingsClosed = useCallback(() => {
    setSettingsChanged((v) => v + 1);
    browserPanel.refreshBrowserEnabled();
  }, [browserPanel.refreshBrowserEnabled]);

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
        {(browserActive || browserPanel.browserState?.launched) && (
          <MainTabBar
            activeMainTab={activeMainTab}
            onTabChange={setActiveMainTab}
            browserLoading={browserPanel.browserLoading}
          />
        )}

        <div className="flex flex-1 min-h-0 min-w-0">
          <div
            className={
              activeMainTab === "browser"
                ? "flex flex-1 min-h-0 min-w-0"
                : "hidden"
            }
          >
            <BrowserWorkspace
              state={browserPanel.browserState}
              loading={browserPanel.browserLoading}
              error={browserPanel.browserError}
              actions={browserPanel.browserActions}
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
              onClearActions={browserPanel.clearActions}
              profiles={browserPanel.profiles}
              cookies={browserPanel.cookies}
              cookiesLoading={browserPanel.cookiesLoading}
              onLoadProfile={browserPanel.handleLoadProfile}
              sessionId={activeSessionId ?? ""}
              filterSchema={filterSchema}
              loginForm={loginFormInfo}
              onFiltersApplied={browserPanel.refreshBrowser}
              onCloseBrowser={() => {
                void closeBrowser().then(() => browserPanel.refreshBrowser());
              }}
            />
          </div>

          <div
            className={
              activeMainTab === "chat"
                ? "flex flex-1 min-h-0 min-w-0"
                : "hidden"
            }
          >
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
          </div>
        </div>
      </div>

      <SchemaSidebar
        tables={tables}
        schemaLoading={schemaLoading}
        runs={runs}
        activeSessionId={activeSessionId}
        highlightedRunId={highlightedRunId}
        showSchemaSql={showSchemaSql}
        browserState={browserPanel.browserState}
        browserLoading={browserPanel.browserLoading}
        browserEnabled={browserPanel.browserEnabled}
        onViewBrowser={() => setActiveMainTab("browser")}
        profiles={browserPanel.profiles}
        profilesLoading={browserPanel.profilesLoading}
        cookies={browserPanel.cookies}
        cookiesLoading={browserPanel.cookiesLoading}
        onSaveProfile={browserPanel.handleSaveProfile}
        onLoadProfile={browserPanel.handleLoadProfile}
        onDeleteProfile={browserPanel.handleDeleteProfile}
        onUpdateProfile={browserPanel.handleUpdateProfile}
        onDeleteCookie={browserPanel.handleDeleteCookie}
        onClearCookies={browserPanel.handleClearCookies}
        onRefreshCookies={browserPanel.refreshCookies}
      />

      <AppDialogs
        workspace={workspace}
        workspaces={workspaces}
        workspacesError={workspacesError}
        switchingWorkspace={switchingWorkspace}
        settingsOpen={settingsOpen}
        onSettingsOpenChange={setSettingsOpen}
        onSettingsChanged={handleSettingsClosed}
        showSessionIdHover={showSessionIdHover}
        setShowSessionIdHover={setShowSessionIdHover}
        showSchemaSql={showSchemaSql}
        setShowSchemaSql={setShowSchemaSql}
        undoConfirmGroupId={undoConfirmGroupId}
        onUndoConfirmClose={() => setUndoConfirmGroupId(null)}
        onUndoConfirm={handleRevertConfirm}
        approvalRequest={approvalRequest}
        filterSchema={filterSchema}
        onApprovalSubmit={handleApprovalSubmit}
        onSwitchWorkspace={handleSwitchWorkspace}
        onCreateWorkspace={onCreateWorkspace}
        onRenameWorkspace={onRenameWorkspace}
        onDeleteWorkspace={onDeleteWorkspace}
        onRefreshWorkspaces={onRefreshWorkspaces}
        isPickerOpen={pickerOpen}
        onPickerClose={handleCloseWorkspacePicker}
        onOpenPicker={handleOpenWorkspacePicker}
      />
    </div>
  );
}
