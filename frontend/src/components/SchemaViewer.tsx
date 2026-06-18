import { Accordion } from "@heroui/react";
import { ChevronDown } from "lucide-react";
import type { SchemaTable } from "../types";
import SchemaColumnList from "./SchemaColumnList";

interface SchemaViewerProps {
  tables: SchemaTable[];
  loading: boolean;
  showSql: boolean;
}

export default function SchemaViewer({ tables, loading, showSql }: SchemaViewerProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="px-2 py-1 text-xs font-semibold uppercase text-muted tracking-wide">
        Schema
      </span>
      {loading && (
        <p className="px-2 py-2 text-xs text-muted">Loading...</p>
      )}
      {!loading && tables.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted">No tables found</p>
      )}
      {!loading && tables.length > 0 && (
        <Accordion className="w-full" hideSeparator>
          {tables.map((table) => (
            <Accordion.Item key={table.name} id={table.name}>
              <Accordion.Heading>
                <Accordion.Trigger>
                  <code className="truncate text-xs">{table.name}</code>
                  <Accordion.Indicator>
                    <ChevronDown className="h-3 w-3" />
                  </Accordion.Indicator>
                </Accordion.Trigger>
              </Accordion.Heading>
              <Accordion.Panel>
                <Accordion.Body>
                  <div className="flex flex-col gap-2 py-1">
                    <SchemaColumnList columns={table.columns} />
                    {showSql && (
                      <pre className="overflow-x-auto rounded-md bg-default/30 p-2 text-xs text-muted mt-1">
                        {table.sql}
                      </pre>
                    )}
                  </div>
                </Accordion.Body>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
    </div>
  );
}
