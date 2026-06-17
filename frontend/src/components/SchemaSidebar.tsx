import { useCallback, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import type { SchemaTable } from "../types";
import SchemaViewer from "./SchemaViewer";

interface SchemaSidebarProps {
  tables: SchemaTable[];
  schemaLoading: boolean;
}

export default function SchemaSidebar({
  tables,
  schemaLoading,
}: SchemaSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  if (collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-3 border-l py-3">
        <button
          className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
          onClick={toggleCollapse}
          aria-label="Expand schema sidebar"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <span className="font-semibold text-foreground">Schema</span>
        <button
          className="rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
          onClick={toggleCollapse}
          aria-label="Collapse schema sidebar"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        <SchemaViewer tables={tables} loading={schemaLoading} />
      </div>
    </aside>
  );
}
