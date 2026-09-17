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
            <pre className="text-xs text-muted whitespace-pre-wrap wrap-break-word max-h-48 overflow-y-auto font-mono">
              {output || t("tool.no_output")}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
