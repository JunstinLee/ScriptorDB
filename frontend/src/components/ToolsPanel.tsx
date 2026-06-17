import { useState } from "react";
import {
  Wrench,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  FileText,
  Database,
  Terminal,
  BarChart3,
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
    }
  }

  if (writes.length > 0) {
    ops.push({
      icon: <FileText className="h-3 w-3" />,
      label: `新建文件: ${writes.join(", ")}`,
    });
  }
  if (charts > 0) {
    ops.push({
      icon: <BarChart3 className="h-3 w-3" />,
      label: `生成图表`,
    });
  }
  if (queries > 0) {
    ops.push({
      icon: <Database className="h-3 w-3" />,
      label: `查询数据库`,
    });
  }
  if (pythons > 0) {
    ops.push({
      icon: <Terminal className="h-3 w-3" />,
      label: `执行 Python 代码`,
    });
  }
  return ops;
}

function getCollapsedSummary(invocations: TI[]): string {
  const ops = getOperations(invocations);
  if (ops.length === 0) return `${invocations.length} 个工具`;
  return ops.map((op) => op.label).join(" · ");
}

interface ToolsPanelProps {
  runs: Run[];
}

export default function ToolsPanel({ runs }: ToolsPanelProps) {
  const [collapsedRounds, setCollapsedRounds] = useState<Set<number>>(
    new Set(),
  );
  const [collapsedTools, setCollapsedTools] = useState<Set<number>>(
    new Set(),
  );

  const runsWithTools = runs.filter((r) => r.tool_invocations.length > 0);

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

  if (runsWithTools.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted">
        <Wrench className="h-8 w-8 mb-2 opacity-40" />
        <p className="text-sm">暂无工具调用</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {runsWithTools.map((run) => {
        const roundIndex = runs.indexOf(run) + 1;
        const isRoundCollapsed = collapsedRounds.has(roundIndex);
        const isToolsCollapsed = collapsedTools.has(roundIndex);
        const operations = getOperations(run.tool_invocations);
        const collapsedSummary = getCollapsedSummary(run.tool_invocations);

        return (
          <div
            key={run.run_id}
            className="rounded-lg border border-default-200 overflow-hidden"
          >
            {/* 轮次标题 */}
            <button
              type="button"
              onClick={() => toggleRound(roundIndex)}
              className="flex items-center gap-2 w-full px-3 py-2 bg-default-100/50 border-b border-default-200 text-left hover:bg-default-100 transition-colors"
            >
              {isRoundCollapsed ? (
                <ChevronRight className="h-3 w-3 text-muted shrink-0" />
              ) : (
                <ChevronDown className="h-3 w-3 text-muted shrink-0" />
              )}
              <MessageSquare className="h-3 w-3 text-muted shrink-0" />
              <span className="text-xs font-medium text-muted shrink-0">
                第 {roundIndex} 轮
              </span>
              {isRoundCollapsed && (
                <span className="text-xs text-default-400 truncate">
                  · {collapsedSummary}
                </span>
              )}
            </button>

            {/* 展开内容 */}
            {!isRoundCollapsed && (
              <>
                {/* 操作摘要区 */}
                {operations.length > 0 && (
                  <div className="px-3 py-2.5 bg-default-50 border-b border-default-200">
                    <div className="text-[10px] font-medium text-default-400 uppercase tracking-wide mb-1.5">
                      操作
                    </div>
                    <div className="flex flex-col gap-1">
                      {operations.map((op, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-2 text-xs text-muted"
                        >
                          <span className="text-default-400">{op.icon}</span>
                          <span>{op.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 工具调用区 */}
                <div className="p-2">
                  <button
                    type="button"
                    onClick={() => toggleTools(roundIndex)}
                    className="flex items-center gap-1.5 w-full text-left px-1 py-1 hover:bg-default-50 rounded transition-colors"
                  >
                    {isToolsCollapsed ? (
                      <ChevronRight className="h-3 w-3 text-muted shrink-0" />
                    ) : (
                      <ChevronDown className="h-3 w-3 text-muted shrink-0" />
                    )}
                    <Wrench className="h-3 w-3 text-muted shrink-0" />
                    <span className="text-xs font-medium text-muted">
                      工具调用 ({run.tool_invocations.length})
                    </span>
                  </button>
                  {!isToolsCollapsed && (
                    <div className="flex flex-col gap-1.5 mt-1.5">
                      {run.tool_invocations.map((inv) => (
                        <ToolInvocation key={inv.call_id} invocation={inv} />
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
