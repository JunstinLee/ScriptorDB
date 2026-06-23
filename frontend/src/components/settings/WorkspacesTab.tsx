import { Button, Label } from "@heroui/react";
import { FolderOpen } from "lucide-react";
import type { WorkspaceDetail } from "../../types";

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
}: WorkspacesTabProps) {
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
