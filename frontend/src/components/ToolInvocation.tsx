import { useCallback, useState } from "react";
import { Chip, Spinner } from "@heroui/react";
import { ChevronDown, Check, X, Clock, Copy } from "lucide-react";
import type { ToolInvocation as ToolInvocationType } from "../types";
import { t } from "../i18n";

interface ToolInvocationProps {
  invocation: ToolInvocationType;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function previewSql(sql: string): string {
  return sql.length > 30 ? sql.slice(0, 27) + t("tool.preview_ellipsis") : sql;
}

function getToolSummary(toolName: string, args: Record<string, unknown>): string {
  switch (toolName) {
    case "run_python_code":
      return t("tool.summary.ran_python_code");

    case "write_csv": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return t("tool.summary.created_csv", {
        filename: filename || t("tool.default_csv_filename"),
      });
    }

    case "write_file": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return t("tool.summary.created_file", {
        filename: filename || t("tool.default_filename"),
      });
    }

    case "export_excel": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return t("tool.summary.exported_excel", {
        filename: filename || t("tool.default_filename"),
      });
    }

    case "read_csv": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return t("tool.summary.read_csv", {
        filename: filename || t("tool.default_csv_filename"),
      });
    }

    case "read_file": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return t("tool.summary.read_file", {
        filename: filename || t("tool.default_filename"),
      });
    }

    case "list_files": {
      const dir = (args.directory as string) || ".";
      return t("tool.summary.listed_directory", { directory: dir });
    }

    case "query_database": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return t("tool.summary.queried_database");
      const upper = sql.toUpperCase();
      if (upper.startsWith("SELECT") || upper.startsWith("WITH")) {
        return t("tool.summary.queried_database_with_sql", { preview: previewSql(sql) });
      }
      return t("tool.summary.queried_database");
    }

    case "get_schema": {
      const table = args.table as string;
      return table
        ? t("tool.summary.fetched_schema", { table })
        : t("tool.summary.fetched_all_schemas");
    }

    case "plot_chart": {
      const type = (args.chart_type as string) || t("tool.default_chart_type");
      const title = (args.title as string) || "";
      return title
        ? t("tool.summary.generated_chart_titled", { type, title })
        : t("tool.summary.generated_chart", { type });
    }

    case "create_table": {
      const tableName = (args.table_name as string) || "";
      const columns = args.columns as Array<{ name: string }> | undefined;
      const colCount = columns?.length || 0;
      return tableName
        ? t("tool.summary.created_table_named", { tableName, colCount })
        : t("tool.summary.created_table");
    }

    case "execute_ddl": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return t("tool.summary.executed_ddl");
      return t("tool.summary.executed_ddl_with_sql", { preview: previewSql(sql) });
    }

    case "write_data": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return t("tool.summary.wrote_data");
      const upper = sql.toUpperCase();
      const opKey = upper.startsWith("INSERT")
        ? "tool.summary.inserted_data"
        : upper.startsWith("UPDATE")
          ? "tool.summary.updated_data"
          : upper.startsWith("DELETE")
            ? "tool.summary.deleted_data"
            : "tool.summary.wrote_data_with_sql";
      return t(opKey, { preview: previewSql(sql) });
    }

    default:
      return t("tool.summary.executed");
  }
}

function getStatusText(
  status: "running" | "success" | "error",
  output: string | undefined,
  error_code: string | undefined,
): string {
  if (status === "running") return t("tool.status_text.running");
  if (status === "error") return error_code || t("tool.status_text.error_no_code");
  if (status === "success") {
    if (!output) return t("tool.status_text.success_empty");
    if (output.length > 50) return output.slice(0, 47) + t("tool.preview_ellipsis");
    return output;
  }
  return "";
}

function extractErrorId(message: string | undefined): string | null {
  if (!message) return null;
  const match = message.match(/（ID: ([^)）]+)）/);
  if (match) return match[1];
  const enMatch = message.match(/\(ID: ([^)]+)\)/);
  return enMatch?.[1] ?? null;
}

function isInternalError(error_code: string | undefined): boolean {
  return (
    error_code === "internal_error" || error_code === "external_service_error"
  );
}

export default function ToolInvocation({ invocation }: ToolInvocationProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const { tool_name, status, output, error_code, duration_ms } = invocation;

  const summary = getToolSummary(tool_name, invocation.args);
  const statusText = getStatusText(status, output, error_code);
  const errorId = extractErrorId(output);
  const showCopyButton = isInternalError(error_code) && errorId != null;

  const handleCopyErrorId = useCallback(async () => {
    if (!errorId) return;
    try {
      await navigator.clipboard.writeText(errorId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable
    }
  }, [errorId]);

  return (
    <div className="border border-grid rounded-md overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-default/30 transition-colors"
      >
        {status === "running" && (
          <Spinner size="sm" className="text-warning" aria-label="Running" />
        )}
        {status === "success" && (
          <Check className="h-3.5 w-3.5 text-sage" aria-label="Success" />
        )}
        {status === "error" && (
          <X className="h-3.5 w-3.5 text-vermilion" aria-label="Error" />
        )}

        <code className="text-xs font-medium text-foreground font-mono">
          {tool_name}
        </code>

        {duration_ms != null && (
          <span className="flex items-center gap-1 text-xs text-muted">
            <Clock className="h-3 w-3" />
            {formatDuration(duration_ms)}
          </span>
        )}

        <Chip
          size="sm"
          variant="soft"
          color={
            status === "success"
              ? "success"
              : status === "error"
                ? "danger"
                : "warning"
          }
        >
          {status === "running"
            ? t("tool.status.running")
            : status === "success"
              ? t("tool.status.success")
              : t("tool.status.error")}
        </Chip>

        <ChevronDown
          className={`h-3.5 w-3.5 text-muted ml-auto transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </button>



      <div
        className={`tool-expand ${
          expanded && (output || error_code)
            ? "tool-expand-open"
            : "tool-expand-collapsed"
        }`}
      >
        {(output || error_code) && (
          <div className="border-t border-grid px-3 py-2">
            {error_code && (
              <div className="mb-1 flex items-center gap-1.5">
                <Chip size="sm" color="danger" variant="soft">
                  {error_code}
                </Chip>
                {showCopyButton && (
                  <button
                    type="button"
                    onClick={handleCopyErrorId}
                    className="text-xs text-muted hover:text-foreground transition-colors flex items-center gap-1"
                    title={t("tool.copy_error_id")}
                    >
                    {copied ? (
                      <Check className="h-3 w-3 text-sage" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                    <span>{copied ? t("tool.copied") : t("tool.copy")}</span>
                  </button>
                )}
              </div>
            )}
            <pre className="text-xs text-muted whitespace-pre-wrap break-words max-h-48 overflow-y-auto font-mono">
              {output || t("tool.no_output")}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
