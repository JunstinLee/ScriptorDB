import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import {
  Wrench,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { BrowserState, Run, ToolInvocation as TI } from "../types";
import ToolInvocation from "./ToolInvocation";
import { BrowserContextCard } from "./BrowserContextCard";

interface OperationItem {
  icon: React.ReactNode;
  label: string;
}

function getOperations(t: TFunction, invocations: TI[]): OperationItem[] {
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
      case "python_sandbox_execute":
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
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.file")}
        </span>
      ),
      label: t("tool.summary.created_file", { filename: name }),
    });
  }
  if (charts > 0) {
    ops.push({
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.chart")}
        </span>
      ),
      label:
        charts > 1
          ? t("tool.summary.generated_chart_multi", { count: charts })
          : t("tool.summary.generated_chart_simple"),
    });
  }
  if (queries > 0) {
    ops.push({
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.query")}
        </span>
      ),
      label:
        queries > 1
          ? t("tool.summary.queried_database_multi", { count: queries })
          : t("tool.summary.queried_database"),
    });
  }
  if (pythons > 0) {
    ops.push({
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.python")}
        </span>
      ),
      label:
        pythons > 1
          ? t("tool.summary.ran_python_multi", { count: pythons })
          : t("tool.summary.ran_python_simple"),
    });
  }
  if (dbCreates > 0) {
    ops.push({
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.ddl")}
        </span>
      ),
      label:
        dbCreates > 1
          ? t("tool.summary.created_table_multi", { count: dbCreates })
          : t("tool.summary.created_table"),
    });
  }
  if (dbWrites > 0) {
    ops.push({
      icon: (
        <span className="font-mono text-[11px] text-muted">
          {t("tool.tag.db")}
        </span>
      ),
      label: t("tool.summary.wrote_database"),
    });
  }
  return ops;
}

function getCollapsedSummary(t: TFunction, invocations: TI[]): string {
  const ops = getOperations(t, invocations);
  if (ops.length === 0) {
    return t("tool.summary.tools_count", { count: invocations.length });
  }
  return ops.map((op) => op.label).join(" · ");
}

interface ToolsPanelProps {
  runs: Run[];
  highlightedRunId: string | null;
  browserState: BrowserState | null;
  browserLoading: boolean;
  onViewBrowser: () => void;
}

export default function ToolsPanel({ runs, highlightedRunId, browserState, browserLoading, onViewBrowser }: ToolsPanelProps) {
  const { t } = useTranslation();
  const [collapsedRounds, setCollapsedRounds] = useState<Set<number>>(
    new Set(),
  );
  const [collapsedTools, setCollapsedTools] = useState<Set<number>>(
    new Set(),
  );

  const runsWithTools = runs.filter((r) => r.tool_invocations.length > 0);
  const prevRunIdsRef = useRef<string[]>([]);

  console.log(
    "[ToolsPanel] runsWithTools: %d runs, run_ids=%s",
    runsWithTools.length,
    runsWithTools
      .map(
        (r) =>
          r.run_id +
          "[" +
          r.tool_invocations
            .map((t) => t.call_id + ":" + t.status)
            .join(",") +
          "]",
      )
      .join(" | "),
  );

  const runsRef = useRef(runs);
  const runsWithToolsRef = useRef(runsWithTools);

  // ref 同步放到 effect 中，避免渲染期间更新 ref（react-hooks/refs）
  useEffect(() => {
    runsRef.current = runs;
    runsWithToolsRef.current = runsWithTools;
  }, [runs, runsWithTools]);

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

  // run 集合变化时同步折叠状态：
  // 会话切换（完全换掉）全部展开；出现新一轮时只设定一次默认态（旧轮次折叠、最新一轮展开），
  // 之后尊重用户的手动操作，面板不再自己变形
  useEffect(() => {
    const ids = runsWithTools.map((r) => r.run_id);
    const prev = prevRunIdsRef.current;
    if (ids.length > 0 && !ids.some((id) => prev.includes(id))) {
      setCollapsedRounds(new Set());
      setCollapsedTools(new Set());
    } else if (ids.length > prev.length) {
      setCollapsedRounds(new Set(ids.slice(0, -1).map((_, i) => i + 1)));
      setCollapsedTools(new Set());
    }
    prevRunIdsRef.current = ids;
  }, [runsWithTools]);

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
      <div className="flex flex-col gap-1 py-6">
        <p className="text-[13px] text-foreground">{t("tool.empty")}</p>
        <p className="text-[11px] text-muted">{t("tool.empty_hint")}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      <BrowserContextCard
        state={browserState}
        loading={browserLoading}
        onViewInMain={onViewBrowser}
      />
      {runsWithTools.map((run) => {
        const runIndex = runsWithTools.findIndex((r) => r.run_id === run.run_id);
        const runNumber = runIndex + 1;
        const isRoundCollapsed = collapsedRounds.has(runNumber);
        const isToolsCollapsed = collapsedTools.has(runNumber);
        const collapsedSummary = getCollapsedSummary(t, run.tool_invocations);

        return (
          <div
            key={run.run_id}
            data-run-id={run.run_id}
            className={`rounded-lg border border-default overflow-hidden ${
              run.run_id === highlightedRunId ? "run-highlight" : ""
            }`}
          >
            <button
              type="button"
              onClick={() => toggleRound(runNumber)}
              className="flex items-center gap-2 w-full px-3 py-2 bg-default/30 border-b border-default text-left hover:bg-default/50 transition-colors"
            >
              {isRoundCollapsed ? (
                <ChevronRight className="h-3 w-3 text-muted shrink-0" />
              ) : (
                <ChevronDown className="h-3 w-3 text-muted shrink-0" />
              )}
              <span className="font-mono text-[11px] font-semibold text-muted shrink-0">
                {t("tool.run_label", { count: runNumber })}
              </span>
              {isRoundCollapsed && (
                <span className="text-[11px] text-muted truncate">
                  · {collapsedSummary}
                </span>
              )}
            </button>

            <div
              className={`tool-expand ${
                isRoundCollapsed ? "tool-expand-collapsed" : "tool-expand-open"
              }`}
            >
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
                  <span className="text-[11px] font-semibold text-muted">
                    {t("tool.invocations", {
                      count: run.tool_invocations.length,
                    })}
                  </span>
                </button>
                <div
                  className={`tool-expand ${
                    isToolsCollapsed
                      ? "tool-expand-collapsed"
                      : "tool-expand-open"
                  }`}
                >
                  <div className="flex flex-col divide-y divide-default mt-1.5">
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
