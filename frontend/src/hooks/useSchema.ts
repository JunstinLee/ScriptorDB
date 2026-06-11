import { useCallback, useEffect, useState } from "react";
import type { SchemaTable } from "../types";
import { getSchema } from "../api/client";

export function useSchema() {
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSchema = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSchema();
      setTables(res.tables);
    } catch {
      setTables([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSchema();
  }, [fetchSchema]);

  return { tables, loading, refresh: fetchSchema };
}
