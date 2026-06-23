import { useCallback, useEffect, useState } from "react";
import type { SchemaTable } from "../types";
import { getSchema } from "../api/client";

export function useSchema(workspaceId?: string | null) {
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSchema = useCallback(async () => {
    if (workspaceId === null || workspaceId === undefined) {
      setTables([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await getSchema();
      setTables(res.tables);
    } catch {
      setTables([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void fetchSchema();
  }, [fetchSchema]);

  return { tables, loading, refresh: fetchSchema };
}
