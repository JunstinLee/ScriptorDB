import { useCallback, useEffect, useState } from "react";
import { Button, Label, Switch } from "@heroui/react";
import { Trash2 } from "lucide-react";
import {
  deleteSession,
  listSessions,
  updateSettings,
} from "../../api/client";
import type { SessionListItem, SettingsResponse } from "../../types";
import { formatRelative, getSessionDisplayName } from "../../utils/display";

interface SessionsTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
  onSessionsChanged?: () => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
  showSchemaSql: boolean;
  setShowSchemaSql: (v: boolean) => void;
}

export default function SessionsTab({
  settings,
  onSettingsChange,
  onSessionsChanged,
  showSessionIdHover,
  setShowSessionIdHover,
  showSchemaSql,
  setShowSchemaSql,
}: SessionsTabProps) {
  const [items, setItems] = useState<SessionListItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [toggling, setToggling] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listSessions();
      setItems(res.sessions);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggleAutoRestore = useCallback(
    async (next: boolean) => {
      setToggling(true);
      try {
        const updated = await updateSettings({ auto_restore_sessions: next });
        onSettingsChange(updated);
      } catch (e) {
        console.error(e);
      } finally {
        setToggling(false);
      }
    },
    [onSettingsChange],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between rounded-lg border border-grid bg-surface p-3">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm font-medium">
            Auto-restore sessions on restart
          </Label>
          <p className="text-xs text-muted">
            When enabled, the server re-loads previous sessions on startup and
            this UI restores your last active session.
          </p>
        </div>
        <Switch
          isSelected={settings.auto_restore_sessions}
          onChange={(v) => void handleToggleAutoRestore(v)}
          isDisabled={toggling}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-grid bg-surface p-3">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm font-medium">
            Show session ID on hover
          </Label>
          <p className="text-xs text-muted">
            When enabled, hovering over a session name shows the underlying
            session ID as a tooltip.
          </p>
        </div>
        <Switch
          isSelected={showSessionIdHover}
          onChange={(v) => void setShowSessionIdHover(v)}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-grid bg-surface p-3">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm font-medium">
            Show CREATE SQL in schema
          </Label>
          <p className="text-xs text-muted">
            When enabled, the CREATE TABLE SQL is displayed below the column
            list in the schema sidebar.
          </p>
        </div>
        <Switch
          isSelected={showSchemaSql}
          onChange={(v) => void setShowSchemaSql(v)}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">History</h3>
          <Button
            size="sm"
            variant="ghost"
            onPress={() => void refresh()}
            isDisabled={loading}
          >
            Refresh
          </Button>
        </div>

        {items === null ? (
          <div className="py-4 text-center text-sm text-muted">Loading…</div>
        ) : items.length === 0 ? (
          <div className="py-4 text-center text-sm text-muted">
            No sessions yet. Start a new session to ask about your data.
          </div>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {items.map((s) => {
              const displayName = getSessionDisplayName(s.title);
              return (
                <li
                  key={s.session_id}
                  className="flex items-center gap-3 rounded-lg border border-grid bg-surface px-3 py-2"
                >
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span
                      className="truncate text-sm font-medium"
                      title={showSessionIdHover ? s.session_id : displayName}
                    >
                      {displayName}
                    </span>
                    <span className="text-xs text-muted">
                      {s.message_count} message{s.message_count === 1 ? "" : "s"} ·
                      last active {formatRelative(s.last_access)}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    isIconOnly
                    aria-label={`Delete ${displayName}`}
                    onPress={async () => {
                      try {
                        await deleteSession(s.session_id);
                        await refresh();
                        onSessionsChanged?.();
                      } catch (e) {
                        console.error(e);
                      }
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
