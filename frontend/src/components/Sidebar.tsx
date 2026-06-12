import { useCallback, useEffect, useState } from "react";
import { Switch } from "@heroui/react";
import {
  Database,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import type { SchemaTable } from "../types";
import SchemaViewer from "./SchemaViewer";
import SessionList from "./SessionList";

interface SessionMeta {
  session_id: string;
  created_at: string;
  title: string;
}

interface SidebarProps {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  tables: SchemaTable[];
  schemaLoading: boolean;
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
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onOpenSettings,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const html = document.documentElement;
    if (isDark) {
      html.classList.add("dark");
      html.setAttribute("data-theme", "dark");
    } else {
      html.classList.remove("dark");
      html.setAttribute("data-theme", "light");
    }
  }, [isDark]);

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

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
          <button
            className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {isDark ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </button>
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
        <Switch
          isSelected={isDark}
          onChange={toggleTheme}
          size="sm"
        >
          <Switch.Control>
            <Switch.Thumb>
              <Switch.Icon>
                {isDark ? (
                  <Moon className="h-3 w-3" />
                ) : (
                  <Sun className="h-3 w-3" />
                )}
              </Switch.Icon>
            </Switch.Thumb>
          </Switch.Control>
          <Switch.Content>
            <span className="text-xs font-medium">
              {isDark ? "Dark Mode" : "Light Mode"}
            </span>
          </Switch.Content>
        </Switch>
      </div>
    </aside>
  );
}
