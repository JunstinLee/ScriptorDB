import { useCallback, useState } from "react";
import { Chip, Spinner } from "@heroui/react";
import { ChevronDown, Check, X, Clock, Copy } from "lucide-react";
import type { ToolInvocation as ToolInvocationType } from "../types";

interface ToolInvocationProps {
  invocation: ToolInvocationType;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function getToolSummary(toolName: string, args: Record<string, unknown>): string {
  switch (toolName) {
    case "run_python_code":
      return "Ran Python code";

    case "write_csv": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return `Created CSV: ${filename || "output.csv"}`;
    }

    case "write_file": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return `Created file: ${filename || "file"}`;
    }

    case "export_excel": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return `Exported Excel: ${filename || "file"}`;
    }

    case "read_csv": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return `Read CSV: ${filename || "output.csv"}`;
    }

    case "read_file": {
      const path = (args.filepath as string) || "";
      const filename = path.split("/").pop() || path;
      return `Read file: ${filename || "file"}`;
    }

    case "list_files": {
      const dir = (args.directory as string) || ".";
      return `Listed directory: ${dir}`;
    }

    case "query_database": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return "Queried database";
      const upper = sql.toUpperCase();
      if (upper.startsWith("SELECT") || upper.startsWith("WITH")) {
        const preview = sql.length > 30 ? sql.slice(0, 27) + "..." : sql;
        return `Queried database: ${preview}`;
      }
      return "Queried database";
    }

    case "get_schema": {
      const table = args.table as string;
      return table ? `Fetched schema: ${table}` : "Fetched all table schemas";
    }

    case "plot_chart": {
      const type = (args.chart_type as string) || "chart";
      const title = (args.title as string) || "";
      return title
        ? `Generated ${type} chart: ${title}`
        : `Generated ${type} chart`;
    }

    case "create_table": {
      const tableName = (args.table_name as string) || "";
      const columns = args.columns as Array<{ name: string }> | undefined;
      const colCount = columns?.length || 0;
      return tableName
        ? `Created table ${tableName} (${colCount} columns)`
        : "Created table";
    }

    case "execute_ddl": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return "Executed DDL";
      const preview = sql.length > 30 ? sql.slice(0, 27) + "..." : sql;
      return `Executed DDL: ${preview}`;
    }

    case "write_data": {
      const sql = ((args.sql as string) || "").trim();
      if (!sql) return "Wrote data";
      const upper = sql.toUpperCase();
      const op = upper.startsWith("INSERT")
        ? "Inserted"
        : upper.startsWith("UPDATE")
          ? "Updated"
          : upper.startsWith("DELETE")
            ? "Deleted"
            : "Wrote";
      const preview = sql.length > 30 ? sql.slice(0, 27) + "..." : sql;
      return `${op}: ${preview}`;
    }

    default:
      return "Executed";
  }
}

function getStatusText(
  status: "running" | "success" | "error",
  output: string | undefined,
  error_code: string | undefined,
): string {
  if (status === "running") return "Running";
  if (status === "error") return error_code || "Failed";
  if (status === "success") {
    if (!output) return "Done";
    if (output.length > 50) return output.slice(0, 47) + "...";
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
          {status === "running" ? "Running" : status === "success" ? "OK" : "Error"}
        </Chip>

        <ChevronDown
          className={`h-3.5 w-3.5 text-muted ml-auto transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </button>

      <div className="px-3 py-1.5 bg-default/10 border-t border-grid">
        <span className="text-xs text-muted">{summary}</span>
        {status !== "running" && statusText && (
          <span className="text-xs text-muted ml-2">— {statusText}</span>
        )}
      </div>

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
                    title="Copy error ID"
                  >
                    {copied ? (
                      <Check className="h-3 w-3 text-sage" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                )}
              </div>
            )}
            <pre className="text-xs text-muted whitespace-pre-wrap break-words max-h-48 overflow-y-auto font-mono">
              {output || "(no output)"}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
