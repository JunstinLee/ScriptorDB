import { useCallback, useState } from "react";
import { Label, Switch } from "@heroui/react";
import { updateSettings } from "../../api/client";
import type { SettingsResponse } from "../../types";

interface SessionsTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
  showSchemaSql: boolean;
  setShowSchemaSql: (v: boolean) => void;
}

export default function SessionsTab({
  settings,
  onSettingsChange,
  showSessionIdHover,
  setShowSessionIdHover,
  showSchemaSql,
  setShowSchemaSql,
}: SessionsTabProps) {
  const [toggling, setToggling] = useState(false);

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
    </div>
  );
}
