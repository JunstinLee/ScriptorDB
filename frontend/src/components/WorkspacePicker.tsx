import { useCallback, useState } from "react";
import { Button, Input, Label } from "@heroui/react";
import { FolderOpen, Plus, RefreshCw, Trash2 } from "lucide-react";
import type {
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "../types";
import AlertBanner from "./common/AlertBanner";

interface WorkspacePickerProps {
  workspaces: WorkspaceItem[];
  activeWorkspace: WorkspaceDetail | null;
  error: string | null;
  onActivate: (id: string) => Promise<WorkspaceDetail>;
  onCreate: (body: WorkspaceCreateRequest) => Promise<WorkspaceDetail>;
  onRename: (id: string, body: WorkspaceUpdateRequest) => Promise<WorkspaceDetail>;
  onDelete: (id: string, deleteFiles?: boolean) => Promise<void>;
  onRefresh: () => Promise<void>;
  onCancelActive: () => void;
}

interface CreateFormState {
  name: string;
  path: string;
  dbUrl: string;
  showAdvanced: boolean;
}

const EMPTY_CREATE: CreateFormState = {
  name: "",
  path: "",
  dbUrl: "",
  showAdvanced: false,
};

export default function WorkspacePicker({
  workspaces,
  activeWorkspace,
  error,
  onActivate,
  onCreate,
  onRename,
  onDelete,
  onRefresh,
  onCancelActive,
}: WorkspacePickerProps) {
  const [createForm, setCreateForm] = useState<CreateFormState>(EMPTY_CREATE);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const handleSubmitCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!createForm.name.trim() || !createForm.path.trim()) {
        setLocalError("Name and path are required");
        return;
      }
      setBusy(true);
      setLocalError(null);
      try {
        await onCreate({
          name: createForm.name.trim(),
          path: createForm.path.trim(),
          db_url: createForm.dbUrl.trim() || null,
        });
        setCreateForm(EMPTY_CREATE);
      } catch (err) {
        setLocalError(err instanceof Error ? err.message : "Failed to create workspace");
      } finally {
        setBusy(false);
      }
    },
    [createForm, onCreate],
  );

  const handleActivate = useCallback(
    async (id: string) => {
      setBusy(true);
      setLocalError(null);
      try {
        await onActivate(id);
      } catch (err) {
        setLocalError(err instanceof Error ? err.message : "Failed to switch workspace");
      } finally {
        setBusy(false);
      }
    },
    [onActivate],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      const ws = workspaces.find((w) => w.id === id);
      if (!ws) return;
      const isActive = activeWorkspace?.id === id;
      const message = isActive
        ? `Delete active workspace "${ws.name}"? This will remove it from the registry.`
        : `Delete workspace "${ws.name}"?`;
      if (!window.confirm(`${message}\n\nTip: choose "Delete files" to also remove the directory contents.`)) {
        return;
      }
      const deleteFiles = window.confirm(
        "Also remove the workspace directory contents?\n\nClick OK to delete files, Cancel to keep them.",
      );
      setBusy(true);
      setLocalError(null);
      try {
        await onDelete(id, deleteFiles);
        if (isActive) onCancelActive();
      } catch (err) {
        setLocalError(err instanceof Error ? err.message : "Failed to delete workspace");
      } finally {
        setBusy(false);
      }
    },
    [workspaces, activeWorkspace, onDelete, onCancelActive],
  );

  const handleStartRename = useCallback((ws: WorkspaceItem) => {
    setRenamingId(ws.id);
    setRenameValue(ws.name);
  }, []);

  const handleCommitRename = useCallback(
    async (id: string) => {
      const name = renameValue.trim();
      if (!name) {
        setRenamingId(null);
        return;
      }
      setBusy(true);
      setLocalError(null);
      try {
        await onRename(id, { name });
        setRenamingId(null);
      } catch (err) {
        setLocalError(err instanceof Error ? err.message : "Failed to rename workspace");
      } finally {
        setBusy(false);
      }
    },
    [renameValue, onRename],
  );

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background px-4">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl border bg-surface shadow-lg">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Workspaces</h1>
            <p className="text-xs text-muted">
              Each workspace has its own database, sessions, and API keys.
            </p>
          </div>
          <Button
            variant="ghost"
            isIconOnly
            aria-label="Refresh workspaces"
            onPress={() => void onRefresh()}
          >
            <RefreshCw className="size-4" />
          </Button>
        </div>

        <div className="max-h-[55vh] overflow-y-auto px-6 py-4 space-y-2">
          {(localError || error) && (
            <AlertBanner
              variant="error"
              message={localError ?? error ?? ""}
            />
          )}

          {workspaces.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted">
              No workspaces yet. Create one to get started.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {workspaces.map((ws) => {
                const isActive = activeWorkspace?.id === ws.id;
                const isRenaming = renamingId === ws.id;
                return (
                  <li
                    key={ws.id}
                    className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${
                      isActive ? "border-accent/40 bg-accent/5" : "bg-surface/50"
                    }`}
                  >
                    <div className="flex min-w-0 flex-1 flex-col">
                      {isRenaming ? (
                        <Input
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              void handleCommitRename(ws.id);
                            } else if (e.key === "Escape") {
                              setRenamingId(null);
                            }
                          }}
                        />
                      ) : (
                        <span className="truncate text-sm font-medium">
                          {ws.name}
                          {isActive && (
                            <span className="ml-2 text-xs text-accent">active</span>
                          )}
                        </span>
                      )}
                      <span
                        className="truncate text-xs text-muted font-mono"
                        title={ws.path}
                      >
                        {ws.path}
                      </span>
                    </div>
                    {isRenaming ? (
                      <>
                        <Button
                          size="sm"
                          variant="primary"
                          isDisabled={busy}
                          onPress={() => void handleCommitRename(ws.id)}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onPress={() => setRenamingId(null)}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          variant="primary"
                          isDisabled={busy || isActive}
                          onPress={() => void handleActivate(ws.id)}
                        >
                          {isActive ? "Active" : "Open"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          isIconOnly
                          aria-label={`Rename ${ws.name}`}
                          onPress={() => handleStartRename(ws)}
                        >
                          <FolderOpen className="size-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          isIconOnly
                          aria-label={`Delete ${ws.name}`}
                          onPress={() => void handleDelete(ws.id)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <form
          onSubmit={handleSubmitCreate}
          className="space-y-3 border-t bg-surface/50 px-6 py-4"
        >
          <div className="flex items-center gap-2">
            <Plus className="size-4 text-muted" />
            <h2 className="text-sm font-semibold">New workspace</h2>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ws-name">Name</Label>
              <Input
                id="ws-name"
                name="name"
                placeholder="My project"
                value={createForm.name}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, name: e.target.value }))
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ws-path">Path</Label>
              <Input
                id="ws-path"
                name="path"
                placeholder="/absolute/path/to/project"
                value={createForm.path}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, path: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-xs text-muted hover:text-foreground"
              onClick={() =>
                setCreateForm((prev) => ({
                  ...prev,
                  showAdvanced: !prev.showAdvanced,
                }))
              }
            >
              {createForm.showAdvanced ? "▾" : "▸"} Advanced
            </button>
          </div>

          {createForm.showAdvanced && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ws-dburl">DB URL (optional)</Label>
              <Input
                id="ws-dburl"
                name="db_url"
                placeholder="sqlite:///<path>/db.sqlite"
                value={createForm.dbUrl}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, dbUrl: e.target.value }))
                }
              />
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onPress={() => setCreateForm(EMPTY_CREATE)}
              isDisabled={busy}
            >
              Reset
            </Button>
            <Button
              type="submit"
              variant="primary"
              isDisabled={busy}
            >
              {busy ? "Creating…" : "Create & open"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
