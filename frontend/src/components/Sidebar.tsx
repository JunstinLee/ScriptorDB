import { useCallback, useRef, useState } from "react";
import { Popover } from "@heroui/react";
import {
  ChevronDown,
  Folder,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings as SettingsIcon,
} from "lucide-react";
import type { SessionMeta, WorkspaceDetail, WorkspaceItem } from "../types";
import HistorySearchModal from "./HistorySearchModal";
import SessionList from "./SessionList";
import ThemeToggle from "./common/ThemeToggle";
import WorkspacePath from "./common/WorkspacePath";

interface SidebarProps {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  showSessionIdHover: boolean;
  onNewSession: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onOpenSettings: () => void;
  activeWorkspace: WorkspaceDetail | null;
  workspaces: WorkspaceItem[];
  switchingWorkspace: boolean;
  onSwitchWorkspace: (id: string) => void;
  onOpenWorkspacePicker: () => void;
  onRequestNewWorkspace: () => void;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  showSessionIdHover,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onOpenSettings,
  activeWorkspace,
  workspaces,
  switchingWorkspace,
  onSwitchWorkspace,
  onOpenWorkspacePicker,
  onRequestNewWorkspace,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [popoverWidth, setPopoverWidth] = useState(232);

  const handleSelectWorkspace = useCallback(
    (id: string) => {
      if (activeWorkspace && id === activeWorkspace.id) return;
      onSwitchWorkspace(id);
    },
    [activeWorkspace, onSwitchWorkspace],
  );

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const measureTrigger = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    setPopoverWidth(Math.max(160, Math.round(el.getBoundingClientRect().width)));
  }, []);

  if (collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-2 overflow-x-hidden border-r py-3">
        <button
          type="button"
          className="rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={onOpenWorkspacePicker}
          disabled={switchingWorkspace}
          aria-label="Open workspace picker"
          title={activeWorkspace?.name ?? "No workspace"}
        >
          <Folder className="size-4" />
        </button>
        <button
          type="button"
          className="rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={toggleCollapsed}
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <PanelLeftOpen className="size-4" />
        </button>
        <div className="my-1 h-px w-6 bg-grid" aria-hidden />
        <button
          type="button"
          className="rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={onNewSession}
          aria-label="New session"
          title="New session"
        >
          <MessageSquarePlus className="size-4" />
        </button>
        <button
          type="button"
          className="rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={() => setIsHistoryOpen(true)}
          aria-label="Search history"
          title="Search history"
        >
          <Search className="size-4" />
        </button>
        <div className="flex-1" />
        <ThemeToggle variant="icon" />
        <button
          type="button"
          className="rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={onOpenSettings}
          aria-label="Open settings"
        >
          <SettingsIcon className="size-4" />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-[260px] shrink-0 flex-col overflow-x-hidden border-r">
      {/* Top section: Workspace selector */}
      <div className="px-4 py-3">
        <Popover>
          <Popover.Trigger>
            <button
              ref={triggerRef}
              type="button"
              className="box-border flex w-[220px] min-w-0 items-center gap-2 rounded-lg border border-grid bg-surface px-3 py-2 text-left transition-colors hover:bg-surface/70 focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
              disabled={switchingWorkspace}
              aria-label="Switch workspace"
              onClick={measureTrigger}
            >
              <Folder className="size-4 shrink-0 text-graphite" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-ink">
                  {activeWorkspace?.name ?? "No workspace"}
                </div>
                <WorkspacePath
                  path={activeWorkspace?.path}
                  className="text-[11px] text-graphite font-mono"
                />
              </div>
              <ChevronDown className="size-3.5 shrink-0 text-graphite" />
            </button>
          </Popover.Trigger>
          <Popover.Content
            placement="bottom"
            className="p-0"
            style={{ width: `${popoverWidth}px`, maxWidth: `${popoverWidth}px` }}
          >
            <Popover.Dialog className="p-1">
              <div className="px-2 py-1.5 text-xs text-muted">
                Current workspace
              </div>
              <div className="rounded-md border-l-[3px] border-l-cobalt bg-surface px-3 py-2">
                <div className="truncate text-sm font-medium">
                  {activeWorkspace?.name ?? "No workspace"}
                </div>
                <WorkspacePath
                  path={activeWorkspace?.path}
                  className="text-xs text-muted font-mono"
                />
              </div>

              {workspaces.filter((w) => w.id !== activeWorkspace?.id).length > 0 && (
                <>
                  <div className="mt-2 px-2 py-1.5 text-xs text-muted">
                    Switch to
                  </div>
                  <ul className="flex flex-col gap-0.5">
                    {workspaces
                      .filter((w) => w.id !== activeWorkspace?.id)
                      .map((w) => (
                        <li key={w.id}>
                          <button
                            type="button"
                            className="flex w-full min-w-0 flex-col items-stretch rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-surface"
                            onClick={() => handleSelectWorkspace(w.id)}
                          >
                            <span className="truncate font-medium">
                              {w.name}
                            </span>
                            <WorkspacePath
                              path={w.path}
                              className="text-xs text-muted font-mono"
                            />
                          </button>
                        </li>
                      ))}
                  </ul>
                </>
              )}

              <div className="mt-2 flex flex-col gap-0.5 border-t border-grid pt-2">
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-surface"
                  onClick={onRequestNewWorkspace}
                >
                  <Plus className="size-3.5" /> New workspace
                </button>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-surface"
                  onClick={onOpenWorkspacePicker}
                >
                  <Folder className="size-3.5" /> Manage workspaces
                </button>
              </div>
            </Popover.Dialog>
          </Popover.Content>
        </Popover>
      </div>

      {/* Divider with collapse button — at the end of the workspace area */}
      <div className="flex items-center justify-end gap-1 border-b border-grid px-3 py-1">
        <span className="flex-1" />
        <button
          type="button"
          className="rounded-md p-1 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={toggleCollapsed}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <PanelLeftClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Middle section: Sessions */}
      <div className="flex-1 overflow-y-auto py-2">
        <div className="px-4 pb-2">
          <button
            type="button"
            onClick={() => setIsHistoryOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] font-medium text-graphite transition-colors hover:bg-surface hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
            aria-label="Search history"
          >
            <Search className="size-4" />
            <span>Search history</span>
          </button>
        </div>

        <SessionList
          sessions={sessions}
          activeSessionId={activeSessionId}
          showSessionIdHover={showSessionIdHover}
          onNewSession={onNewSession}
          onSwitchSession={onSwitchSession}
          onDeleteSession={onDeleteSession}
        />
      </div>

      {/* Bottom section: Theme + Settings */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-grid">
        <ThemeToggle variant="switch" />
        <button
          className="rounded-lg p-1.5 text-graphite transition-colors hover:bg-surface hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
          onClick={onOpenSettings}
          aria-label="Open settings"
        >
          <SettingsIcon className="h-4 w-4" />
        </button>
      </div>

      {isHistoryOpen && (
        <HistorySearchModal
          isOpen={isHistoryOpen}
          onClose={() => setIsHistoryOpen(false)}
          onSelectSession={(id) => {
            onSwitchSession(id);
            setIsHistoryOpen(false);
          }}
        />
      )}
    </aside>
  );
}
