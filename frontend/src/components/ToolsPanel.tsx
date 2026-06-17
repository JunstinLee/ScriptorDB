import { Wrench } from "lucide-react";
import type { Run } from "../types";
import ToolInvocation from "./ToolInvocation";

interface ToolsPanelProps {
  runs: Run[];
}

export default function ToolsPanel({ runs }: ToolsPanelProps) {
  const runsWithTools = runs.filter((r) => r.tool_invocations.length > 0);

  if (runsWithTools.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted">
        <Wrench className="h-8 w-8 mb-2 opacity-40" />
        <p className="text-sm">暂无工具调用</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {runsWithTools.map((run) => (
        <div key={run.run_id} className="flex flex-col gap-1.5">
          {run.tool_invocations.map((inv) => (
            <ToolInvocation key={inv.call_id} invocation={inv} />
          ))}
        </div>
      ))}
    </div>
  );
}
