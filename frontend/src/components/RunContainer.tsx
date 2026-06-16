import { useState } from "react";
import { Chip, Spinner } from "@heroui/react";
import { ChevronDown, Check, X, Wrench } from "lucide-react";
import type { Run } from "../types";
import ToolInvocation from "./ToolInvocation";
import TraceList from "./TraceList";

interface RunContainerProps {
  run: Run;
}

export default function RunContainer({ run }: RunContainerProps) {
  const [expanded, setExpanded] = useState(true);
  const hasActivity =
    run.tool_invocations.length > 0 || run.trace_steps.length > 0;
  const toolCount = run.tool_invocations.length;
  const errorCount = run.tool_invocations.filter(
    (t) => t.status === "error",
  ).length;

  return (
    <div className="border border-default-200 rounded-xl overflow-hidden bg-surface">
      {/* Status header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-default-50">
        {run.status === "running" && <Spinner size="sm" />}
        {run.status === "completed" && (
          <Check className="h-4 w-4 text-success" />
        )}
        {run.status === "error" && <X className="h-4 w-4 text-danger" />}

        <Chip
          size="sm"
          variant="soft"
          color={
            run.status === "running"
              ? "warning"
              : run.status === "completed"
                ? "success"
                : "danger"
          }
        >
          {run.status === "running"
            ? "Running"
            : run.status === "completed"
              ? "Done"
              : "Error"}
        </Chip>

        {hasActivity && (
          <span className="text-xs text-muted">
            {toolCount > 0 && (
              <>
                <Wrench className="inline h-3 w-3 mr-0.5" />
                {toolCount} tool{toolCount !== 1 ? "s" : ""}
                {errorCount > 0 && (
                  <span className="text-danger">
                    {" "}
                    ({errorCount} failed)
                  </span>
                )}
              </>
            )}
          </span>
        )}

        {hasActivity && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="ml-auto flex items-center gap-1 text-xs text-muted hover:text-foreground transition-colors"
          >
            {expanded ? "Collapse" : "Expand"}
            <ChevronDown
              className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        )}
      </div>

      {/* Trace + Tools (expandable) */}
      {expanded && hasActivity && (
        <div className="border-t border-default-200 px-3 py-2 space-y-2">
          {run.trace_steps.length > 0 && (
            <TraceList steps={run.trace_steps} />
          )}
          {run.tool_invocations.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {run.tool_invocations.map((inv) => (
                <ToolInvocation key={inv.call_id} invocation={inv} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Final output */}
      {run.final_output && (
        <div className="border-t border-default-200 px-4 py-3">
          <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
            {run.final_output}
          </div>
        </div>
      )}

      {/* Error message */}
      {run.status === "error" && run.error_message && (
        <div className="border-t border-danger/20 bg-danger/5 px-4 py-3">
          <p className="text-sm text-danger">{run.error_message}</p>
        </div>
      )}
    </div>
  );
}
