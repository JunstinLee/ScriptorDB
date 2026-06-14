import { useCallback, useState } from "react";
import {
  Database,
  PanelLeftClose,
  PanelLeftOpen,
  Settings as SettingsIcon,
} from "lucide-react";
import type { SchemaTable, SessionMeta } from "../types";
import SchemaViewer from "./SchemaViewer";
import SessionList from "./SessionList";
import ThemeToggle from "./common/ThemeToggle";

interface SidebarProps {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  tables: SchemaTable[];
  schemaLoading: boolean;
  showSessionIdHover: boolean;
  onNewSession: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onOpenSettings: () => void;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  tables,
  schemaLoading,
  showSessionIdHover,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onOpenSettings,
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

        <div className="px-2">
          <hr className="border-separator" />
        </div>

        <SchemaViewer tables={tables} loading={schemaLoading} />
      </div>

      <div className="border-t px-4 py-3">
        <ThemeToggle variant="switch" />
      </div>
    </aside>
  );
}
