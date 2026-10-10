import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { MessageSquarePlus } from "lucide-react";
import type { SchemaTable, WorkspaceDetail } from "../types";
import WorkspacePath from "./common/WorkspacePath";

interface WelcomeScreenProps {
  workspace: WorkspaceDetail | null;
  tables: SchemaTable[];
  onNewSession: () => void;
}

function tablePrompt(t: TFunction, tableName: string, index: number): string {
  const prompts = [
    t("chat.table_prompt.rows", { name: tableName }),
    t("chat.table_prompt.columns", { name: tableName }),
    t("chat.table_prompt.count", { name: tableName }),
    t("chat.table_prompt.schema", { name: tableName }),
    t("chat.table_prompt.describe", { name: tableName }),
  ];
  return prompts[index % prompts.length];
}

export default function WelcomeScreen({ workspace, tables, onNewSession }: WelcomeScreenProps) {
  const { t } = useTranslation();
  const displayTables = tables.slice(0, 5);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6">
      <div className="flex flex-col items-center gap-2 max-w-130 w-full">
        <h1 className="font-mono text-[24px] font-semibold text-ink leading-[1.2]">
          ScriptorDB
        </h1>

        {workspace && (
          <div className="flex flex-col items-center gap-0.5">
            <span className="text-[13px] font-medium text-ink">
              {workspace.name}
            </span>
            <WorkspacePath
              path={workspace.path}
              className="text-[11px] text-graphite font-mono max-w-100"
            />
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
                  {tablePrompt(t, table.name, i).split("**").map((part, j) =>
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
            {t("session.new")}
          </Button>
          <span className="text-[13px] text-graphite">
            {t("chat.welcome_hint")}
          </span>
        </div>
      </div>
    </div>
  );
}
