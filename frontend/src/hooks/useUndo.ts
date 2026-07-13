import { useCallback, useState } from "react";
import { listUndoGroups, revertAndTrimSession } from "../api/client";
import type { UndoGroup } from "../types";

export function useUndo() {
  const [groups, setGroups] = useState<UndoGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listUndoGroups();
      setGroups(data.groups);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load undo groups");
    } finally {
      setLoading(false);
    }
  }, []);

  const revertData = useCallback(async (groupId: number) => {
    const { revertUndoGroup } = await import("../api/client");
    setError(null);
    try {
      const result = await revertUndoGroup(groupId);
      await refresh();
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Revert failed");
      throw e;
    }
  }, [refresh]);

  const revertAndTrim = useCallback(async (groupId: number) => {
    setError(null);
    try {
      const result = await revertAndTrimSession(groupId);
      await refresh();
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Revert and trim failed");
      throw e;
    }
  }, [refresh]);

  return { groups, loading, error, refresh, revertData, revertAndTrim };
}
