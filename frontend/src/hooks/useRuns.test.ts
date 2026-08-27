import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRuns } from "./useRuns";
import type { StreamRunEvent, Run, ToolCallRunEvent } from "../types";

const T0 = "2025-01-01T00:00:00.000Z";

function runStart(runId: string, timestamp = T0): StreamRunEvent {
  return { type: "run_start", run_id: runId, timestamp };
}

function textDelta(runId: string, delta: string): StreamRunEvent {
  return { type: "text_delta", run_id: runId, delta };
}

function trace(runId: string, step: number, message: string): StreamRunEvent {
  return { type: "trace", run_id: runId, step, message, timestamp: T0 };
}

function toolCall(callId: string, toolName = "get_schema"): ToolCallRunEvent {
  return {
    type: "tool_call",
    run_id: "r1",
    call_id: callId,
    tool_name: toolName,
    args: { table: "users" },
    timestamp: T0,
  };
}

function toolResult(callId: string, success: boolean, output = "ok"): StreamRunEvent {
  return {
    type: "tool_result",
    run_id: "r1",
    call_id: callId,
    tool_name: "get_schema",
    success,
    output,
    error_code: success ? undefined : "E42",
    duration_ms: 12,
    timestamp: T0,
  };
}

describe("useRuns", () => {
  it("starts with no runs for any session", () => {
    const { result } = renderHook(() => useRuns());

    expect(result.current.runsBySession).toEqual({});
    expect(result.current.getRuns("s1")).toEqual([]);
  });

  it("creates a running run on run_start", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
    });

    const runs = result.current.getRuns("s1");
    expect(runs).toHaveLength(1);
    expect(runs[0]).toMatchObject({
      run_id: "r1",
      status: "running",
      started_at: T0,
      tool_invocations: [],
      trace_steps: [],
      final_output: "",
    });
  });

  it("ignores duplicate run_start events for the same run", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", runStart("r1"));
    });

    expect(result.current.getRuns("s1")).toHaveLength(1);
  });

  it("accumulates text_delta into final_output", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", textDelta("r1", "Hel"));
      result.current.appendEvent("s1", textDelta("r1", "lo"));
    });

    expect(result.current.getRuns("s1")[0].final_output).toBe("Hello");
  });

  it("creates a run implicitly when an event arrives without run_start", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", textDelta("r9", "orphan"));
    });

    const runs = result.current.getRuns("s1");
    expect(runs).toHaveLength(1);
    expect(runs[0].run_id).toBe("r9");
    expect(runs[0].final_output).toBe("orphan");
  });

  it("appends tool_call as a running invocation", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", toolCall("c1"));
    });

    const inv = result.current.getRuns("s1")[0].tool_invocations[0];
    expect(inv).toMatchObject({
      call_id: "c1",
      tool_name: "get_schema",
      args: { table: "users" },
      status: "running",
      started_at: T0,
    });
  });

  it("updates invocation status and output on matching tool_result", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", toolCall("c1"));
      result.current.appendEvent("s1", toolResult("c1", true, "3 tables"));
    });

    const inv = result.current.getRuns("s1")[0].tool_invocations[0];
    expect(inv).toMatchObject({
      status: "success",
      output: "3 tables",
      duration_ms: 12,
      ended_at: T0,
    });
  });

  it("marks invocation error on failed tool_result", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", toolCall("c1"));
      result.current.appendEvent("s1", toolResult("c1", false, "boom"));
    });

    const inv = result.current.getRuns("s1")[0].tool_invocations[0];
    expect(inv.status).toBe("error");
    expect(inv.error_code).toBe("E42");
  });

  it("leaves invocations untouched when tool_result has no matching call_id", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", toolCall("c1"));
      result.current.appendEvent("s1", toolResult("c2", true));
    });

    const inv = result.current.getRuns("s1")[0].tool_invocations[0];
    expect(inv.status).toBe("running");
    expect(inv.output).toBeUndefined();
  });

  it("appends trace steps", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", trace("r1", 1, "connecting"));
      result.current.appendEvent("s1", trace("r1", 2, "querying"));
    });

    expect(result.current.getRuns("s1")[0].trace_steps).toEqual([
      { step: 1, message: "connecting", timestamp: T0 },
      { step: 2, message: "querying", timestamp: T0 },
    ]);
  });

  it("marks run completed and keeps final_output on metadata", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", textDelta("r1", "partial"));
      result.current.appendEvent("s1", {
        type: "metadata",
        run_id: "r1",
        full_output: "final answer",
      });
    });

    const run = result.current.getRuns("s1")[0];
    expect(run.status).toBe("completed");
    expect(run.final_output).toBe("final answer");
    expect(run.ended_at).toBeDefined();
  });

  it("marks run error with message on error event", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", {
        type: "error",
        run_id: "r1",
        message: "rate limited",
        error_type: "rate_limit",
      });
    });

    const run = result.current.getRuns("s1")[0];
    expect(run.status).toBe("error");
    expect(run.error_message).toBe("rate limited");
    expect(run.error_type).toBe("rate_limit");
    expect(run.ended_at).toBeDefined();
  });

  it("marks run completed with ended_at on run_end", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", {
        type: "run_end",
        run_id: "r1",
        timestamp: T0,
      });
    });

    const run = result.current.getRuns("s1")[0];
    expect(run.status).toBe("completed");
    expect(run.ended_at).toBe(T0);
  });

  it("appends browser_action events", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s1", {
        type: "browser_action",
        run_id: "r1",
        tool: "browser_click",
        action: "click",
        url: "https://example.com",
        timestamp: T0,
      });
    });

    expect(result.current.getRuns("s1")[0].browser_actions).toHaveLength(1);
  });

  it("setRuns replaces the session run list authoritatively", () => {
    const { result } = renderHook(() => useRuns());

    const serverRuns: Run[] = [
      {
        run_id: "r9",
        status: "completed",
        tool_invocations: [],
        trace_steps: [],
        final_output: "server",
        started_at: T0,
      },
    ];

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.setRuns("s1", serverRuns);
    });

    expect(result.current.getRuns("s1")).toEqual(serverRuns);
  });

  it("clearRuns removes a single session", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s2", runStart("r2"));
      result.current.clearRuns("s1");
    });

    expect(result.current.getRuns("s1")).toEqual([]);
    expect(result.current.getRuns("s2")).toHaveLength(1);
  });

  it("clearRuns without sessionId clears everything", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s2", runStart("r2"));
      result.current.clearRuns();
    });

    expect(result.current.runsBySession).toEqual({});
  });

  it("keeps runs of different sessions separate", () => {
    const { result } = renderHook(() => useRuns());

    act(() => {
      result.current.appendEvent("s1", runStart("r1"));
      result.current.appendEvent("s2", runStart("r2"));
    });

    expect(result.current.getRuns("s1")[0].run_id).toBe("r1");
    expect(result.current.getRuns("s2")[0].run_id).toBe("r2");
  });
});
