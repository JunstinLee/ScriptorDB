import type { Run } from "../types";
import TraceList from "./TraceList";

interface RunContainerProps {
  run: Run;
}

export default function RunContainer({ run }: RunContainerProps) {
  return (
    <div className="rounded-xl overflow-hidden">
      {run.final_output && (
        <div className="px-4 py-3">
          <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
            {run.final_output}
          </div>
        </div>
      )}

      {run.trace_steps.length > 0 && (
        <div className="border-t border-divider px-4 py-2">
          <TraceList steps={run.trace_steps} />
        </div>
      )}

      {run.status === "error" && run.error_message && (
        <div className="border-t border-danger/20 bg-danger/5 px-4 py-3">
          <p className="text-sm text-danger">{run.error_message}</p>
        </div>
      )}
    </div>
  );
}
