import { useCallback, useState } from "react";
import {
  Database,
  Folder,
  PanelLeftClose,
  PanelLeftOpen,
  Settings as SettingsIcon,
} from "lucide-react";
import type { SessionMeta, WorkspaceDetail } from "../types";
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
  onOpenWorkspacePicker: () => void;
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
  onOpenWorkspacePicker,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

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
        <button
          type="button"
          onClick={onOpenWorkspacePicker}
          className="flex w-full items-center gap-2 rounded-lg border bg-surface/50 px-2 py-1.5 text-left text-xs hover:bg-default/50"
        >
          <Folder className="size-3.5 text-muted" />
          <span className="truncate font-medium">
            {activeWorkspace?.name ?? "No workspace"}
          </span>
        </button>
        <ThemeToggle variant="switch" />
      </div>
    </aside>
  );
}
