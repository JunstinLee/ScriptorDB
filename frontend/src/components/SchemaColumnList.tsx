import type { SchemaColumn } from "../types";

interface SchemaColumnListProps {
  columns: SchemaColumn[];
}

function columnFlags(col: SchemaColumn): string {
  return [
    col.pk ? "pk" : null,
    col.notnull && !col.pk ? "nn" : null,
    col.autoincrement ? "ai" : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function SchemaColumnList({ columns }: SchemaColumnListProps) {
  if (columns.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-0.5 px-1">
      {columns.map((col) => {
        const flags = columnFlags(col);
        return (
          <div
            key={col.name}
            className="flex items-center gap-2 py-0.5 text-[11px]"
          >
            <code className="shrink-0 font-mono text-foreground">
              {col.name}
            </code>
            <span className="shrink-0 font-mono text-muted">{col.type}</span>
            {flags && (
              <span className="ml-auto shrink-0 font-mono text-[10px] leading-none text-muted">
                {flags}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
