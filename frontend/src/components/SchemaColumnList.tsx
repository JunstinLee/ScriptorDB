import type { SchemaColumn } from "../types";

interface SchemaColumnListProps {
  columns: SchemaColumn[];
}

function ColumnTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded bg-default-200/60 px-1 py-px text-[10px] font-medium leading-none text-default-500">
      {label}
    </span>
  );
}

export default function SchemaColumnList({ columns }: SchemaColumnListProps) {
  if (columns.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-0.5 px-1">
      {columns.map((col) => (
        <div
          key={col.name}
          className="flex items-center gap-2 py-0.5 text-xs"
        >
          <code className="shrink-0 font-mono text-foreground">
            {col.name}
          </code>
          <span className="shrink-0 text-default-400">{col.type}</span>
          <span className="ml-auto flex items-center gap-1">
            {col.pk && <ColumnTag label="PK" />}
            {col.notnull && !col.pk && <ColumnTag label="NN" />}
            {col.autoincrement && <ColumnTag label="AI" />}
          </span>
        </div>
      ))}
    </div>
  );
}
