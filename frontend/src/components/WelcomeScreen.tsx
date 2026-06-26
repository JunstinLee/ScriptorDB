import { Button } from "@heroui/react";
import { MessageSquarePlus } from "lucide-react";
import type { SchemaTable, WorkspaceDetail } from "../types";

interface WelcomeScreenProps {
  workspace: WorkspaceDetail | null;
  tables: SchemaTable[];
  onNewSession: () => void;
}

function tablePrompt(tableName: string, index: number): string {
  const prompts = [
    `Show me the first 10 rows of **${tableName}**`,
    `What columns does **${tableName}** have?`,
    `How many rows are in **${tableName}**?`,
    `Show the schema for **${tableName}**`,
    `Describe the **${tableName}** table`,
  ];
  return prompts[index % prompts.length];
}

export default function WelcomeScreen({ workspace, tables, onNewSession }: WelcomeScreenProps) {
  const displayTables = tables.slice(0, 5);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6">
      <div className="flex flex-col items-center gap-2 max-w-[520px] w-full">
        <h1 className="font-mono text-[24px] font-semibold text-ink leading-[1.2]">
          ScriptorDB
        </h1>

        {workspace && (
          <div className="flex flex-col items-center gap-0.5">
            <span className="text-[13px] font-medium text-ink">
              {workspace.name}
            </span>
            <span className="text-[11px] text-graphite font-mono truncate max-w-[400px]">
              {workspace.path}
            </span>
          </div>
        )}

        {displayTables.length > 0 && (
          <div className="mt-4 flex flex-col items-center gap-2 w-full">
            {displayTables.map((table, i) => (
              <div
                key={table.name}
                className="w-full rounded-lg border border-grid bg-surface/60 px-4 py-2.5 text-center"
              >
                <span className="text-[14px] text-ink leading-relaxed">
                  {tablePrompt(table.name, i).split("**").map((part, j) =>
                    j % 2 === 1 ? (
                      <code
                        key={j}
                        className="font-mono text-[13px] text-cobalt bg-cobalt/8 rounded px-1 py-0.5"
                      >
                        {part}
                      </code>
                    ) : (
                      <span key={j}>{part}</span>
                    ),
                  )}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 flex flex-col items-center gap-3">
          <Button variant="primary" onPress={onNewSession}>
            <MessageSquarePlus className="mr-2 h-4 w-4" />
            New session
          </Button>
          <span className="text-[13px] text-graphite">
            Or type a question about your database below.
          </span>
        </div>
      </div>
    </div>
  );
}
