import { useCallback, useState } from "react";
import MainApp from "./components/MainApp";
import { useWorkspaces } from "./hooks/useWorkspaces";
import type {
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceUpdateRequest,
} from "./types";

export default function App() {
  const {
    workspaces,
    activeWorkspace,
    isLoading: workspacesLoading,
    error: workspacesError,
    refresh: refreshWorkspaces,
    createAndActivate,
    switchWorkspace,
    renameWorkspace,
    removeWorkspace,
  } = useWorkspaces();

  const [switchingWorkspace, setSwitchingWorkspace] = useState(false);

  const handlePickerActivate = useCallback(
    async (id: string): Promise<WorkspaceDetail> => {
      setSwitchingWorkspace(true);
      try {
        return await switchWorkspace(id);
      } finally {
        setSwitchingWorkspace(false);
      }
    },
    [switchWorkspace],
  );

  const handlePickerCreate = useCallback(
    async (body: WorkspaceCreateRequest): Promise<WorkspaceDetail> => {
      setSwitchingWorkspace(true);
      try {
        return await createAndActivate(body);
      } finally {
        setSwitchingWorkspace(false);
      }
    },
    [createAndActivate],
  );

  const handlePickerRename = useCallback(
    async (
      id: string,
      body: WorkspaceUpdateRequest,
    ): Promise<WorkspaceDetail> => {
      return await renameWorkspace(id, body);
    },
    [renameWorkspace],
  );

  const handlePickerDelete = useCallback(
    async (id: string, deleteFiles?: boolean): Promise<void> => {
      await removeWorkspace(id, deleteFiles);
      await refreshWorkspaces();
    },
    [removeWorkspace, refreshWorkspaces],
  );

  if (workspacesLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted">
        <span className="text-sm">Loading workspaces…</span>
      </div>
    );
  }

  return (
    <MainApp
      workspace={activeWorkspace}
      workspaces={workspaces}
      workspacesError={workspacesError}
      switchingWorkspace={switchingWorkspace}
      onSwitchWorkspace={handlePickerActivate}
      onCreateWorkspace={handlePickerCreate}
      onRenameWorkspace={handlePickerRename}
      onDeleteWorkspace={handlePickerDelete}
      onRefreshWorkspaces={refreshWorkspaces}
    />
  );
}
