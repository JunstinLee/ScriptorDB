import { Button, Label } from "@heroui/react";
import { FolderOpen, Upload } from "lucide-react";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { WorkspaceDetail } from "../../types";
import {
  fetchLegacySessionsSummary,
  importLegacySessions,
  type LegacySessionsSummary,
} from "../../api/workspaces";
import WorkspacePath from "../common/WorkspacePath";

interface WorkspacesTabProps {
  activeWorkspace: WorkspaceDetail | null;
  workspacesCount: number;
  onOpenPicker: () => void;
  onWorkspaceChanged: () => void;
}

export default function WorkspacesTab({
  activeWorkspace,
  workspacesCount,
  onOpenPicker,
  onWorkspaceChanged,
}: WorkspacesTabProps) {
  const { t } = useTranslation();
  const [legacySummary, setLegacySummary] = useState<LegacySessionsSummary | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  useEffect(() => {
    fetchLegacySessionsSummary()
      .then(setLegacySummary)
      .catch(() => {});
  }, []);

  const handleImport = async () => {
    if (!activeWorkspace) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await importLegacySessions(activeWorkspace.id);
      setImportResult(
        t("settings.workspaces.imported", { count: result.imported_count }),
      );
      setLegacySummary({ exists: false, count: 0 });
      onWorkspaceChanged();
    } catch (e) {
      setImportResult(
        e instanceof Error ? e.message : t("settings.workspaces.import_failed"),
      );
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-grid bg-surface p-3">
        <div className="flex flex-col gap-1">
          <Label className="text-sm font-medium">
            {t("settings.workspaces.active")}
          </Label>
          {activeWorkspace ? (
            <>
              <span className="truncate text-sm font-medium">
                {activeWorkspace.name}
              </span>
              <WorkspacePath
                path={activeWorkspace.path}
                className="text-xs text-muted font-mono"
              />
              <span
                className="truncate text-xs text-muted"
                title={activeWorkspace.db_url}
              >
                {t("settings.workspaces.db", { url: activeWorkspace.db_url })}
              </span>
              <span className="text-xs text-muted">
                {t("settings.workspaces.llm", {
                  provider: activeWorkspace.llm_provider,
                  model:
                    activeWorkspace.llm_model ??
                    t("settings.workspaces.default_model"),
                })}
              </span>
            </>
          ) : (
            <span className="text-xs text-muted">
              {t("settings.workspaces.no_active")}
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border border-grid bg-surface p-3">
        <Label className="text-sm font-medium">
          {t("settings.workspaces.manage")}
        </Label>
        <p className="text-xs text-muted">
          {t("settings.workspaces.registered", { count: workspacesCount })}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            onPress={onOpenPicker}
          >
            <FolderOpen className="mr-1.5 size-3.5" />
            {t("settings.workspaces.open_picker")}
          </Button>
        </div>
        <p className="text-xs text-muted">
          {t("settings.workspaces.picker_hint")}
        </p>
      </div>

      {legacySummary?.exists && legacySummary.count > 0 && (
        <div className="rounded-lg border border-grid bg-surface p-3">
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">
              {t("settings.workspaces.legacy_found")}
            </Label>
            <p className="text-xs text-muted">
              {t("settings.workspaces.legacy_available", {
                count: legacySummary.count,
              })}
              {legacySummary.earliest && legacySummary.latest && (
                <>
                  {" "}
                  {t("settings.workspaces.legacy_range", {
                    from: new Date(legacySummary.earliest).toLocaleDateString(),
                    to: new Date(legacySummary.latest).toLocaleDateString(),
                  })}
                </>
              )}
            </p>
            <Button
              variant="primary"
              onPress={handleImport}
              isPending={importing}
              isDisabled={!activeWorkspace}
            >
              <Upload className="mr-1.5 size-3.5" />
              {activeWorkspace
                ? t("settings.workspaces.import_to", {
                    name: activeWorkspace.name,
                  })
                : t("settings.workspaces.select_first")}
            </Button>
            {importResult && (
              <p className="text-xs text-muted">{importResult}</p>
            )}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-grid bg-surface p-3">
        <p className="text-xs text-muted">
          <strong className="text-foreground">
            {t("settings.workspaces.heads_up")}
          </strong>{" "}
          {t("settings.workspaces.keys_hint")}
        </p>
      </div>
    </div>
  );
}
