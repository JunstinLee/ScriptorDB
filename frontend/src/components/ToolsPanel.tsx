import { useEffect, useRef, useState } from "react";
import {
  Wrench,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { Run, ToolInvocation as TI } from "../types";
import ToolInvocation from "./ToolInvocation";

interface OperationItem {
  icon: React.ReactNode;
  label: string;
}

function getOperations(invocations: TI[]): OperationItem[] {
  const ops: OperationItem[] = [];
  const writes: string[] = [];
  let charts = 0;
  let queries = 0;
  let pythons = 0;
  let dbWrites = 0;
  let dbCreates = 0;

  for (const inv of invocations) {
    switch (inv.tool_name) {
      case "write_csv":
      case "write_file":
      case "export_excel": {
        const path = (inv.args.filepath as string) || "";
        const name = path.split("/").pop() || path;
        if (name) writes.push(name);
        break;
      }
      case "plot_chart":
        charts++;
        break;
      case "query_database":
        queries++;
        break;
      case "run_python_code":
        pythons++;
        break;
      case "create_table":
        dbCreates++;
        break;
      case "execute_ddl":
      case "write_data":
        dbWrites++;
        break;
    }
  }

  for (const name of writes) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">FILE</span>,
      label: `Created file: ${name}`,
    });
  }
  if (charts > 0) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">CHART</span>,
      label: charts > 1 ? `Generated ${charts} charts` : "Generated chart",
    });
  }
  if (queries > 0) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">QUERY</span>,
      label: queries > 1 ? `Queried database (${queries}x)` : "Queried database",
    });
  }
  if (pythons > 0) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">PY</span>,
      label: pythons > 1 ? `Ran Python (${pythons}x)` : "Ran Python",
    });
  }
  if (dbCreates > 0) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">DDL</span>,
      label: dbCreates > 1 ? `Created ${dbCreates} tables` : "Created table",
    });
  }
  if (dbWrites > 0) {
    ops.push({
      icon: <span className="text-[10px] font-mono text-graphite">DB</span>,
      label: `Wrote to database`,
    });
  }
  return ops;
}

function getCollapsedSummary(invocations: TI[]): string {
  const ops = getOperations(invocations);
  if (ops.length === 0) return `${invocations.length} tools`;
  return ops.map((op) => op.label).join(" · ");
}

interface ToolsPanelProps {
  runs: Run[];
  highlightedRunId: string | null;
}

export default function ToolsPanel({ runs, highlightedRunId }: ToolsPanelProps) {
  const [collapsedRounds, setCollapsedRounds] = useState<Set<number>>(
    new Set(),
  );
  const [collapsedTools, setCollapsedTools] = useState<Set<number>>(
    new Set(),
  );

  const runsWithTools = runs.filter((r) => r.tool_invocations.length > 0);

  const runsRef = useRef(runs);
  runsRef.current = runs;
  const runsWithToolsRef = useRef(runsWithTools);
  runsWithToolsRef.current = runsWithTools;

  const toggleRound = (roundIndex: number) => {
    setCollapsedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(roundIndex)) next.delete(roundIndex);
      else next.add(roundIndex);
      return next;
    });
  };

  const toggleTools = (roundIndex: number) => {
    setCollapsedTools((prev) => {
      const next = new Set(prev);
      if (next.has(roundIndex)) next.delete(roundIndex);
      else next.add(roundIndex);
      return next;
    });
  };

  useEffect(() => {
    if (!highlightedRunId) return;

    const targetRunIndex = runsRef.current.findIndex(
      (r) => r.run_id === highlightedRunId,
    );
    if (targetRunIndex === -1) return;

    const runsWithToolsIndex = runsWithToolsRef.current.findIndex(
      (r) => r.run_id === highlightedRunId,
    );
    const roundIndex = runsWithToolsIndex + 1;

    setCollapsedRounds((prev) => {
      const next = new Set(prev);
      next.delete(roundIndex);
      return next;
    });

    setCollapsedTools((prev) => {
      const next = new Set(prev);
      next.delete(roundIndex);
      return next;
    });

    requestAnimationFrame(() => {
      const prefersReduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      const el = document.querySelector(`[data-run-id="${highlightedRunId}"]`);
      if (el) {
        el.scrollIntoView({
          behavior: prefersReduced ? "auto" : "smooth",
          block: "center",
        });
      }
    });
  }, [highlightedRunId]);

  if (runsWithTools.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted">
        <Wrench className="h-8 w-8 mb-2 opacity-40" />
        <p className="text-sm">No tool calls in this session yet. They appear when the assistant runs actions.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {runsWithTools.map((run) => {
        const runIndex = runsWithTools.findIndex((r) => r.run_id === run.run_id);
        const runNumber = runIndex + 1;
        const isRoundCollapsed = collapsedRounds.has(runNumber);
        const isToolsCollapsed = collapsedTools.has(runNumber);
        const operations = getOperations(run.tool_invocations);
        const collapsedSummary = getCollapsedSummary(run.tool_invocations);

        return (
          <div
            key={run.run_id}
            data-run-id={run.run_id}
            className={`rounded-lg border border-grid overflow-hidden ${
              run.run_id === highlightedRunId ? "run-highlight" : ""
            }`}
          >
            <button
              type="button"
              onClick={() => toggleRound(runNumber)}
              className="flex items-center gap-2 w-full px-3 py-2 bg-default/30 border-b border-grid text-left hover:bg-default/50 transition-colors"
            >
              {isRoundCollapsed ? (
                <ChevronRight className="h-3 w-3 text-muted shrink-0" />
              ) : (
                <ChevronDown className="h-3 w-3 text-muted shrink-0" />
              )}
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted shrink-0 font-mono">
                Run {runNumber}
              </span>
              {isRoundCollapsed && (
                <span className="text-xs text-graphite truncate">
                  · {collapsedSummary}
                </span>
              )}
            </button>

            <div
              className={`tool-expand ${
                isRoundCollapsed ? "tool-expand-collapsed" : "tool-expand-open"
              }`}
            >
              {operations.length > 0 && (
                <div className="px-3 py-2.5 bg-default/10 border-b border-grid">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted mb-1.5">
                    Operations
                  </div>
                  <div className="flex flex-col gap-1">
                    {operations.map((op, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 text-xs text-muted"
                      >
                        {op.icon}
                        <span>{op.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="p-2">
                <button
                  type="button"
                  onClick={() => toggleTools(runNumber)}
                  className="flex items-center gap-1.5 w-full text-left px-1 py-1 hover:bg-default/30 rounded transition-colors"
                >
                  {isToolsCollapsed ? (
                    <ChevronRight className="h-3 w-3 text-muted shrink-0" />
                  ) : (
                    <ChevronDown className="h-3 w-3 text-muted shrink-0" />
                  )}
                  <Wrench className="h-3 w-3 text-muted shrink-0" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                    Tool Invocations ({run.tool_invocations.length})
                  </span>
                </button>
                <div
                  className={`tool-expand ${
                    isToolsCollapsed
                      ? "tool-expand-collapsed"
                      : "tool-expand-open"
                  }`}
                >
                  <div className="flex flex-col gap-1.5 mt-1.5">
                    {run.tool_invocations.map((inv) => (
                      <ToolInvocation key={inv.call_id} invocation={inv} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
