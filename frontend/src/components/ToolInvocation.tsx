import { useState } from "react";
import { Chip } from "@heroui/react";
import { ChevronDown, Check, X, Clock } from "lucide-react";
import type { ToolInvocation as ToolInvocationType } from "../types";

interface ToolInvocationProps {
  invocation: ToolInvocationType;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return "()";
  const parts = entries.map(([, v]) => {
    const val = typeof v === "string" ? v : JSON.stringify(v);
    return val.length > 60 ? val.slice(0, 57) + "..." : val;
  });
  return `(${parts.join(", ")})`;
}

export default function ToolInvocation({ invocation }: ToolInvocationProps) {
  const [expanded, setExpanded] = useState(true);
  const { tool_name, status, output, error_code, duration_ms, args } = invocation;

  return (
    <div className="border border-default-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-default-100 transition-colors"
      >
        {status === "running" && (
          <span className="inline-block h-2 w-2 rounded-full bg-warning animate-pulse" />
        )}
        {status === "success" && (
          <Check className="h-3.5 w-3.5 text-success" />
        )}
        {status === "error" && <X className="h-3.5 w-3.5 text-danger" />}

        <code className="text-xs font-medium text-foreground">{tool_name}</code>
        <span className="text-xs text-muted truncate flex-1">
          {formatArgs(args)}
        </span>

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

      {expanded && (output || error_code) && (
        <div className="border-t border-default-200 px-3 py-2 bg-default-50">
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
