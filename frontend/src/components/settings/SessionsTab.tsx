import { useCallback, useState } from "react";
import { Label, Switch } from "@heroui/react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [toggling, setToggling] = useState(false);

  const handleToggleAutoRestore = useCallback(
    async (next: boolean) => {
      setToggling(true);
      try {
        const updated = await updateSettings({ auto_restore_sessions: next });
        onSettingsChange(updated);
      } catch {
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
            {t("settings.sessions.auto_restore")}
          </Label>
          <p className="text-xs text-muted">
            {t("settings.sessions.auto_restore_hint")}
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
            {t("settings.sessions.show_id")}
          </Label>
          <p className="text-xs text-muted">
            {t("settings.sessions.show_id_hint")}
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
            {t("settings.sessions.show_sql")}
          </Label>
          <p className="text-xs text-muted">
            {t("settings.sessions.show_sql_hint")}
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
