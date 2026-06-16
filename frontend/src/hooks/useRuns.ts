import { useCallback, useRef, useState } from "react";
import type {
  Run,
  StreamRunEvent,
  ToolInvocation,
  ToolCallRunEvent,
  ToolResultRunEvent,
  TraceEvent,
  TextDeltaEvent,
  RunMetadataEvent,
  RunErrorEvent,
} from "../types";

export function useRuns() {
  const [runsBySession, setRunsBySession] = useState<Record<string, Run[]>>({});
  const runsRef = useRef(runsBySession);
  runsRef.current = runsBySession;

  const getRuns = useCallback((sessionId: string): Run[] => {
    return runsBySession[sessionId] ?? [];
  }, [runsBySession]);

  const appendEvent = useCallback(
    (sessionId: string, event: StreamRunEvent) => {
      if (event.type === "run_start") {
        const exists = runsRef.current[sessionId]?.some(
          (r) => r.run_id === event.run_id,
        );
        if (!exists) {
          const run: Run = {
            run_id: event.run_id,
            status: "running",
            tool_invocations: [],
            trace_steps: [],
            final_output: "",
            started_at: event.timestamp,
          };
          setRunsBySession((prev) => ({
            ...prev,
            [sessionId]: [...(prev[sessionId] ?? []), run],
          }));
        }
        return;
      }

      setRunsBySession((prev) => {
        const sessionRuns = prev[sessionId] ?? [];
        return {
          ...prev,
          [sessionId]: sessionRuns.map((run) => {
            if (run.run_id !== event.run_id) return run;

            switch (event.type) {
              case "trace": {
                const step: TraceEvent = event;
                return {
                  ...run,
                  trace_steps: [
                    ...run.trace_steps,
                    {
                      step: step.step,
                      message: step.message,
                      timestamp: step.timestamp,
                    },
                  ],
                };
              }
              case "tool_call": {
                const tc: ToolCallRunEvent = event;
                const inv: ToolInvocation = {
                  call_id: tc.call_id,
                  tool_name: tc.tool_name,
                  args: tc.args,
                  status: "running",
                  started_at: tc.timestamp,
                };
                return {
                  ...run,
                  tool_invocations: [...run.tool_invocations, inv],
                };
              }
              case "tool_result": {
                const tr: ToolResultRunEvent = event;
                return {
                  ...run,
                  tool_invocations: run.tool_invocations.map((inv) =>
                    inv.call_id === tr.call_id
                      ? {
                          ...inv,
                          status: tr.success
                            ? ("success" as const)
                            : ("error" as const),
                          output: tr.output,
                          error_code: tr.error_code,
                          duration_ms: tr.duration_ms,
                          ended_at: tr.timestamp,
                        }
                      : inv,
                  ),
                };
              }
              case "text_delta": {
                const td: TextDeltaEvent = event;
                return {
                  ...run,
                  final_output: run.final_output + td.delta,
                };
              }
              case "metadata": {
                const md: RunMetadataEvent = event;
                return {
                  ...run,
                  status: "completed",
                  final_output: md.full_output || run.final_output,
                  ended_at: new Date().toISOString(),
                };
              }
              case "error": {
                const er: RunErrorEvent = event;
                return {
                  ...run,
                  status: "error",
                  error_message: er.message,
                  ended_at: new Date().toISOString(),
                };
              }
              default:
                return run;
            }
          }),
        };
      });
    },
    [],
  );

  const clearRuns = useCallback((sessionId?: string) => {
    if (sessionId) {
      setRunsBySession((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });
    } else {
      setRunsBySession({});
    }
  }, []);

  return { runsBySession, getRuns, appendEvent, clearRuns };
}
