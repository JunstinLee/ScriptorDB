import { useCallback, useState } from "react";
import { t } from "../i18n";
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
      setError(e instanceof Error ? e.message : t("error.undo_load_failed"));
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
      setError(e instanceof Error ? e.message : t("error.undo_revert_failed"));
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
      setError(e instanceof Error ? e.message : t("error.undo_revert_trim_failed"));
      throw e;
    }
  }, [refresh]);

  return { groups, loading, error, refresh, revertData, revertAndTrim };
}
