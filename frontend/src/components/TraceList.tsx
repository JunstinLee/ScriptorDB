import type { TraceStep } from "../types";

interface TraceListProps {
  steps: TraceStep[];
}

export default function TraceList({ steps }: TraceListProps) {
  if (steps.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2 text-xs text-muted">
          <span className="shrink-0 font-mono text-default-400 w-5 text-right">
            {step.step}
          </span>
          <span className="flex-1">{step.message}</span>
        </div>
      ))}
    </div>
  );
}
