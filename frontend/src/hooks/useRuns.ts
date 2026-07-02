import { useCallback, useReducer } from "react";
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

type RunsAction =
  | { type: "append"; sessionId: string; event: StreamRunEvent }
  | { type: "set"; sessionId: string; runs: Run[] }
  | { type: "clear"; sessionId?: string };

function createDefaultRun(runId: string, timestamp?: string): Run {
  return {
    run_id: runId,
    status: "running",
    tool_invocations: [],
    trace_steps: [],
    final_output: "",
    started_at: timestamp ?? new Date().toISOString(),
  };
}

function applyEventToRun(run: Run, event: StreamRunEvent): Run {
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
    case "run_end": {
      return {
        ...run,
        status: "completed",
        ended_at: event.timestamp,
      };
    }
    default:
      return run;
  }
}

function runsReducer(
  state: Record<string, Run[]>,
  action: RunsAction,
): Record<string, Run[]> {
  switch (action.type) {
    case "append": {
      const { sessionId, event } = action;
      const sessionRuns = state[sessionId] ?? [];

      if (event.type === "run_start") {
        const exists = sessionRuns.some((r) => r.run_id === event.run_id);
        if (exists) return state;
        const run = createDefaultRun(event.run_id, event.timestamp);
        return {
          ...state,
          [sessionId]: [...sessionRuns, run],
        };
      }

      const runIndex = sessionRuns.findIndex((r) => r.run_id === event.run_id);
      const baseRun =
        runIndex !== -1
          ? sessionRuns[runIndex]
          : createDefaultRun(event.run_id, event.timestamp);

      const updatedRun = applyEventToRun(baseRun, event);

      const nextSessionRuns = [...sessionRuns];
      if (runIndex === -1) {
        nextSessionRuns.push(updatedRun);
      } else {
        nextSessionRuns[runIndex] = updatedRun;
      }

      return {
        ...state,
        [sessionId]: nextSessionRuns,
      };
    }
    case "set": {
      const { sessionId, runs } = action;
      // Server-fetched runs are authoritative when loading/reloading a session.
      return {
        ...state,
        [sessionId]: runs,
      };
    }
    case "clear": {
      if (action.sessionId) {
        const next = { ...state };
        delete next[action.sessionId];
        return next;
      }
      return {};
    }
  }
}

export function useRuns() {
  const [runsBySession, dispatch] = useReducer(runsReducer, {});

  const getRuns = useCallback(
    (sessionId: string): Run[] => runsBySession[sessionId] ?? [],
    [runsBySession],
  );

  const appendEvent = useCallback(
    (sessionId: string, event: StreamRunEvent) => {
      dispatch({ type: "append", sessionId, event });
    },
    [],
  );

  const setRuns = useCallback((sessionId: string, runs: Run[]) => {
    dispatch({ type: "set", sessionId, runs });
  }, []);

  const clearRuns = useCallback((sessionId?: string) => {
    dispatch({ type: "clear", sessionId });
  }, []);

  return { runsBySession, getRuns, appendEvent, setRuns, clearRuns };
}
