import { useCallback, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { SchemaTable } from "../types";
import SchemaColumnList from "./SchemaColumnList";

interface SchemaViewerProps {
  tables: SchemaTable[];
  loading: boolean;
  showSql: boolean;
  onTableClick?: (tableName: string) => void;
}

export default function SchemaViewer({
  tables,
  loading,
  showSql,
  onTableClick,
}: SchemaViewerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = useCallback((name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const handleClick = useCallback(
    (name: string) => {
      toggle(name);
      onTableClick?.(name);
    },
    [toggle, onTableClick],
  );

  return (
    <div className="flex flex-col gap-1">
      {loading && (
        <p className="px-2 py-2 text-xs text-muted">Loading...</p>
      )}
      {!loading && tables.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted">No tables found. Add a table or import data to see the schema map.</p>
      )}
      {!loading &&
        tables.length > 0 &&
        tables.map((table) => {
          const isExpanded = expanded.has(table.name);
          return (
            <div key={table.name} className="border-b border-grid last:border-0">
              <button
                type="button"
                onClick={() => handleClick(table.name)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-default/30 transition-colors"
              >
                <code className="truncate text-xs font-semibold">
                  {table.name}
                </code>
                <ChevronDown
                  className={`h-3 w-3 text-graphite shrink-0 transition-transform ${
                    isExpanded ? "rotate-180" : ""
                  }`}
                />
              </button>
              {isExpanded && (
                <div className="flex flex-col gap-2 px-3 pb-3">
                  <SchemaColumnList columns={table.columns} />
                  {showSql && (
                    <pre className="overflow-x-auto rounded-md bg-default/30 p-2 text-xs text-muted mt-1">
                      {table.sql}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
    </div>
  );
}
