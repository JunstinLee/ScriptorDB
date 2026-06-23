import { useCallback, useEffect, useRef, useState } from "react";
import {
  activateWorkspace as apiActivateWorkspace,
  createWorkspace as apiCreateWorkspace,
  deleteWorkspace as apiDeleteWorkspace,
  fetchActiveWorkspace,
  fetchWorkspaces,
  updateWorkspace as apiUpdateWorkspace,
  WorkspaceNotSelectedError,
} from "../api/client";
import type {
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "../types";
import { readActiveWorkspaceId, writeActiveWorkspaceId } from "./useAppSettings";

export interface UseWorkspacesResult {
  workspaces: WorkspaceItem[];
  activeWorkspace: WorkspaceDetail | null;
  isLoading: boolean;
  error: string | null;
  needsWorkspace: boolean;
  refresh: () => Promise<void>;
  createAndActivate: (
    body: WorkspaceCreateRequest,
  ) => Promise<WorkspaceDetail>;
  switchWorkspace: (id: string) => Promise<WorkspaceDetail>;
  renameWorkspace: (id: string, body: WorkspaceUpdateRequest) => Promise<WorkspaceDetail>;
  removeWorkspace: (id: string, deleteFiles?: boolean) => Promise<void>;
  clearActive: () => void;
}

function isWorkspaceNotSelected(err: unknown): boolean {
  return err instanceof WorkspaceNotSelectedError;
}

export function useWorkspaces(): UseWorkspacesResult {
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceDetail | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsWorkspace, setNeedsWorkspace] = useState(false);
  const initRef = useRef(false);

  const loadAll = useCallback(async () => {
    const [listResult, activeResult] = await Promise.allSettled([
      fetchWorkspaces(),
      fetchActiveWorkspace(),
    ]);

    if (listResult.status === "fulfilled") {
      setWorkspaces(listResult.value.workspaces);
    } else {
      setWorkspaces([]);
    }

    if (activeResult.status === "fulfilled") {
      const ws = activeResult.value;
      setActiveWorkspace(ws);
      setNeedsWorkspace(ws === null);
      writeActiveWorkspaceId(ws?.id ?? null);
      if (!ws) {
        const cached = readActiveWorkspaceId();
        if (cached && listResult.status === "fulfilled") {
          const match = listResult.value.workspaces.find(
            (w) => w.id === cached,
          );
          if (match) {
            // we know the id is valid, try activating silently
            try {
              const detail = await apiActivateWorkspace(cached);
              setActiveWorkspace(detail);
              setNeedsWorkspace(false);
              writeActiveWorkspaceId(detail.id);
            } catch {
              writeActiveWorkspaceId(null);
            }
          }
        }
      }
    } else if (isWorkspaceNotSelected(activeResult.reason)) {
      setActiveWorkspace(null);
      setNeedsWorkspace(true);
    } else {
      setError(
        activeResult.reason instanceof Error
          ? activeResult.reason.message
          : "Failed to load workspace",
      );
    }
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        await loadAll();
      } finally {
        setIsLoading(false);
      }
    })();
  }, [loadAll]);

  const refresh = useCallback(async () => {
    await loadAll();
  }, [loadAll]);

  const createAndActivate = useCallback(
    async (body: WorkspaceCreateRequest): Promise<WorkspaceDetail> => {
      const created = await apiCreateWorkspace(body);
      const detail = await apiActivateWorkspace(created.id);
      setWorkspaces((prev) => {
        if (prev.find((w) => w.id === detail.id)) return prev;
        return [...prev, { id: detail.id, name: detail.name, path: detail.path, created_at: detail.created_at }];
      });
      setActiveWorkspace(detail);
      setNeedsWorkspace(false);
      writeActiveWorkspaceId(detail.id);
      return detail;
    },
    [],
  );

  const switchWorkspace = useCallback(
    async (id: string): Promise<WorkspaceDetail> => {
      const detail = await apiActivateWorkspace(id);
      setActiveWorkspace(detail);
      setNeedsWorkspace(false);
      writeActiveWorkspaceId(detail.id);
      return detail;
    },
    [],
  );

  const renameWorkspace = useCallback(
    async (id: string, body: WorkspaceUpdateRequest): Promise<WorkspaceDetail> => {
      const detail = await apiUpdateWorkspace(id, body);
      setWorkspaces((prev) =>
        prev.map((w) => (w.id === id ? { ...w, name: detail.name } : w)),
      );
      setActiveWorkspace((prev) =>
        prev && prev.id === id ? detail : prev,
      );
      return detail;
    },
    [],
  );

  const removeWorkspace = useCallback(
    async (id: string, deleteFiles = false) => {
      await apiDeleteWorkspace(id, deleteFiles);
      setWorkspaces((prev) => prev.filter((w) => w.id !== id));
      setActiveWorkspace((prev) => {
        if (prev && prev.id === id) {
          writeActiveWorkspaceId(null);
          return null;
        }
        return prev;
      });
    },
    [],
  );

  const clearActive = useCallback(() => {
    setActiveWorkspace(null);
    setNeedsWorkspace(true);
    writeActiveWorkspaceId(null);
  }, []);

  return {
    workspaces,
    activeWorkspace,
    isLoading,
    error,
    needsWorkspace,
    refresh,
    createAndActivate,
    switchWorkspace,
    renameWorkspace,
    removeWorkspace,
    clearActive,
  };
}
