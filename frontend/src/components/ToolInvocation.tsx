import { useState } from "react";
import { Chip, Spinner } from "@heroui/react";
import { ChevronDown, Check, X, Clock } from "lucide-react";
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
      return "执行 Python 代码";

    case "write_csv": {
      const path = args.filepath as string || "";
      const filename = path.split("/").pop() || path;
      return `写入 ${filename || "CSV 文件"}`;
    }

    case "write_file": {
      const path = args.filepath as string || "";
      const filename = path.split("/").pop() || path;
      return `写入 ${filename || "文件"}`;
    }

    case "export_excel": {
      const path = args.filepath as string || "";
      const filename = path.split("/").pop() || path;
      return `导出 Excel ${filename || "文件"}`;
    }

    case "read_csv": {
      const path = args.filepath as string || "";
      const filename = path.split("/").pop() || path;
      return `读取 ${filename || "CSV 文件"}`;
    }

    case "read_file": {
      const path = args.filepath as string || "";
      const filename = path.split("/").pop() || path;
      return `读取 ${filename || "文件"}`;
    }

    case "list_files": {
      const dir = args.directory as string || ".";
      return `列出 ${dir} 目录`;
    }

    case "query_database": {
      const sql = (args.sql as string || "").trim();
      if (!sql) return "查询数据库";
      const upper = sql.toUpperCase();
      if (upper.startsWith("SELECT") || upper.startsWith("WITH")) {
        const preview = sql.length > 30 ? sql.slice(0, 27) + "..." : sql;
        return `查询: ${preview}`;
      }
      return "查询数据库";
    }

    case "get_schema": {
      const table = args.table as string;
      return table ? `获取 ${table} 表结构` : "获取所有表结构";
    }

    case "plot_chart": {
      const type = args.chart_type as string || "图表";
      const title = args.title as string || "";
      return title ? `生成 ${type} 图: ${title}` : `生成 ${type} 图表`;
    }

    default:
      return "执行操作";
  }
}

function getStatusText(
  status: "running" | "success" | "error",
  output: string | undefined,
  error_code: string | undefined
): string {
  if (status === "running") return "执行中...";
  if (status === "error") return error_code || "执行失败";
  if (status === "success") {
    if (!output) return "完成";
    if (output.length > 50) return output.slice(0, 47) + "...";
    return output;
  }
  return "";
}

export default function ToolInvocation({ invocation }: ToolInvocationProps) {
  const [expanded, setExpanded] = useState(false);
  const { tool_name, status, output, error_code, duration_ms } = invocation;

  const summary = getToolSummary(tool_name, invocation.args);
  const statusText = getStatusText(status, output, error_code);

  return (
    <div className="border border-default-200 rounded-lg overflow-hidden">
      {/* Title bar */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-default-100 transition-colors"
      >
        {status === "running" && (
          <Spinner size="sm" className="text-warning" />
        )}
        {status === "success" && (
          <Check className="h-3.5 w-3.5 text-success" />
        )}
        {status === "error" && <X className="h-3.5 w-3.5 text-danger" />}

        <code className="text-xs font-medium text-foreground">{tool_name}</code>

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
          className={`h-3.5 w-3.5 text-muted transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {/* Middle layer - status summary */}
      <div className="px-3 py-1.5 bg-default-50 border-t border-default-200">
        <span className="text-xs text-muted">{summary}</span>
        {status !== "running" && statusText && (
          <span className="text-xs text-muted ml-2">— {statusText}</span>
        )}
      </div>

      {/* Expanded details - output/error only */}
      {expanded && (output || error_code) && (
        <div className="border-t border-default-200 px-3 py-2">
          {error_code && (
            <div className="mb-1">
              <Chip size="sm" color="danger" variant="soft">
                {error_code}
              </Chip>
            </div>
          )}
          <pre className="text-xs text-muted whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
            {output || "(no output)"}
          </pre>
        </div>
      )}
    </div>
  );
}
