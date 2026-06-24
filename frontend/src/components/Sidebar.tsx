import { useCallback, useState } from "react";
import { Popover } from "@heroui/react";
import {
  ChevronDown,
  Database,
  Folder,
  FolderOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings as SettingsIcon,
} from "lucide-react";
import type { SessionMeta, WorkspaceDetail, WorkspaceItem } from "../types";
import SessionList from "./SessionList";
import ThemeToggle from "./common/ThemeToggle";

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

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleSelectWorkspace = useCallback(
    (id: string) => {
      if (activeWorkspace && id === activeWorkspace.id) return;
      onSwitchWorkspace(id);
    },
    [activeWorkspace, onSwitchWorkspace],
  );

  if (collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-3 border-r py-3">
        <button
          className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
          onClick={toggleCollapse}
          aria-label="Expand sidebar"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
        <button
          className="rounded-lg p-1.5 hover:bg-default/50 text-accent transition-colors"
          onClick={onNewSession}
          aria-label="New session"
        >
          <Database className="h-4 w-4" />
        </button>
        <div className="mt-auto flex flex-col gap-1">
          <ThemeToggle variant="icon" />
          <button
            className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
            onClick={onOpenSettings}
            aria-label="Open settings"
          >
            <SettingsIcon className="h-4 w-4" />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-accent" />
          <span className="font-semibold text-foreground">ScriptorDB</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
            onClick={onOpenSettings}
            aria-label="Open settings"
          >
            <SettingsIcon className="h-4 w-4" />
          </button>
          <button
            className="rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
            onClick={toggleCollapse}
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-2 space-y-4">
        <SessionList
          sessions={sessions}
          activeSessionId={activeSessionId}
          showSessionIdHover={showSessionIdHover}
          onNewSession={onNewSession}
          onSwitchSession={onSwitchSession}
          onDeleteSession={onDeleteSession}
        />
      </div>

      <div className="border-t px-4 py-3 space-y-2">
        <Popover>
          <Popover.Trigger>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-lg border bg-surface/50 px-2 py-1.5 text-left text-xs hover:bg-default/50"
              disabled={switchingWorkspace}
              aria-label="Switch workspace"
            >
              <Folder className="size-3.5 text-muted" />
              <span className="truncate font-medium flex-1">
                {activeWorkspace?.name ?? "No workspace"}
              </span>
              <ChevronDown className="size-3.5 text-muted" />
            </button>
          </Popover.Trigger>
          <Popover.Content className="w-72 p-0">
            <Popover.Dialog className="p-1">
              <div className="px-2 py-1.5 text-xs text-muted">
                Current workspace
              </div>
              <div className="rounded-md bg-accent/10 px-2 py-1.5">
                <div className="truncate text-sm font-medium">
                  {activeWorkspace?.name ?? "No workspace"}
                </div>
                <div
                  className="truncate text-xs text-muted font-mono"
                  title={activeWorkspace?.path}
                >
                  {activeWorkspace?.path ?? "—"}
                </div>
              </div>

              {workspaces.length > 1 && (
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
                            className="flex w-full flex-col items-start rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
                            onClick={() => handleSelectWorkspace(w.id)}
                          >
                            <span className="truncate font-medium">
                              {w.name}
                            </span>
                            <span
                              className="truncate text-xs text-muted font-mono"
                              title={w.path}
                            >
                              {w.path}
                            </span>
                          </button>
                        </li>
                      ))}
                  </ul>
                </>
              )}

              <div className="mt-2 flex flex-col gap-0.5 border-t pt-2">
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
                  onClick={onRequestNewWorkspace}
                >
                  <Plus className="size-3.5" /> New workspace
                </button>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
                  onClick={onOpenWorkspacePicker}
                >
                  <FolderOpen className="size-3.5" /> Manage workspaces
                </button>
              </div>
            </Popover.Dialog>
          </Popover.Content>
        </Popover>
        <ThemeToggle variant="switch" />
      </div>
    </aside>
  );
}
