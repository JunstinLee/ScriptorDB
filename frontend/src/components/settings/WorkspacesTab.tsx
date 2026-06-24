import { Button, Label } from "@heroui/react";
import { FolderOpen, Upload } from "lucide-react";
import { useState, useEffect } from "react";
import type { WorkspaceDetail } from "../../types";
import {
  fetchLegacySessionsSummary,
  importLegacySessions,
  type LegacySessionsSummary,
} from "../../api/workspaces";

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
      setImportResult(`Imported ${result.imported_count} sessions`);
      setLegacySummary({ exists: false, count: 0 });
      onWorkspaceChanged();
    } catch (e) {
      setImportResult(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border p-3">
        <div className="flex flex-col gap-1">
          <Label className="text-sm font-medium">Active workspace</Label>
          {activeWorkspace ? (
            <>
              <span className="truncate text-sm font-medium">
                {activeWorkspace.name}
              </span>
              <span
                className="truncate text-xs text-muted font-mono"
                title={activeWorkspace.path}
              >
                {activeWorkspace.path}
              </span>
              <span
                className="truncate text-xs text-muted"
                title={activeWorkspace.db_url}
              >
                DB: {activeWorkspace.db_url}
              </span>
              <span className="text-xs text-muted">
                LLM: {activeWorkspace.llm_provider} ·{" "}
                {activeWorkspace.llm_model ?? "(default)"}
              </span>
            </>
          ) : (
            <span className="text-xs text-muted">No active workspace.</span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border p-3">
        <Label className="text-sm font-medium">Manage workspaces</Label>
        <p className="text-xs text-muted">
          {workspacesCount} workspace{workspacesCount === 1 ? "" : "s"} registered.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            onPress={onOpenPicker}
          >
            <FolderOpen className="mr-1.5 size-3.5" />
            Open workspace picker
          </Button>
        </div>
        <p className="text-xs text-muted">
          Use the picker to switch between workspaces, create a new one, rename
          an existing entry, or remove a workspace from the registry. API keys
          and default model settings in the other tabs apply to the active
          workspace.
        </p>
      </div>

      {legacySummary?.exists && legacySummary.count > 0 && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">Legacy sessions found</Label>
            <p className="text-xs text-muted">
              {legacySummary.count} old session{legacySummary.count === 1 ? "" : "s"} available to import.
              {legacySummary.earliest && legacySummary.latest && (
                <> From {new Date(legacySummary.earliest).toLocaleDateString()} to {new Date(legacySummary.latest).toLocaleDateString()}.</>
              )}
            </p>
            <Button
              variant="primary"
              onPress={handleImport}
              isLoading={importing}
              isDisabled={!activeWorkspace}
            >
              <Upload className="mr-1.5 size-3.5" />
              {activeWorkspace ? `Import to ${activeWorkspace.name}` : "Select a workspace first"}
            </Button>
            {importResult && (
              <p className="text-xs text-muted">{importResult}</p>
            )}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-warning/30 bg-warning/5 p-3">
        <p className="text-xs text-muted">
          <strong className="text-foreground">Heads up:</strong> LLM settings
          (API keys, default model) shown in the other tabs are stored per
          workspace. Switching workspaces will load a different set of keys.
        </p>
      </div>
    </div>
  );
}
