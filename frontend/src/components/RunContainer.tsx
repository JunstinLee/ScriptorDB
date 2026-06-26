import type { Run } from "../types";
import TraceList from "./TraceList";
import MarkdownRenderer from "./common/MarkdownRenderer";

interface RunContainerProps {
  run: Run;
}

export default function RunContainer({ run }: RunContainerProps) {
  return (
    <div>
      {run.final_output && (
        <div className="px-4 py-3">
          <MarkdownRenderer content={run.final_output} />
        </div>
      )}

      {run.trace_steps.length > 0 && (
        <div className="border-t border-grid px-4 py-2 font-mono">
          <TraceList steps={run.trace_steps} />
        </div>
      )}

      {run.status === "error" && run.error_message && (
        <div className="border-l-[3px] border-l-vermilion bg-vermilion/5 px-4 py-3">
          <p className="text-sm text-vermilion">{run.error_message}</p>
        </div>
      )}

      {run.status === "running" && !run.final_output && run.trace_steps.length === 0 && (
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-graphite">
            <span>Assistant is working</span>
            <span className="flex gap-0.5">
              <span
                className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <span
                className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <span
                className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
