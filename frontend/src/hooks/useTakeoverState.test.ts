import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTakeoverState } from "./useTakeoverState";

const TAKEOVER_TIMEOUT = 150;

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useTakeoverState", () => {
  it("starts in none phase with full countdown", () => {
    const { result } = renderHook(() => useTakeoverState());

    expect(result.current.info).toMatchObject({
      phase: "none",
      reason: "",
      trigger: "",
      remainingSeconds: TAKEOVER_TIMEOUT,
      runId: "",
    });
  });

  it("enterWaiting sets takeover info and starts countdown", () => {
    const { result } = renderHook(() => useTakeoverState());

    act(() => {
      result.current.enterWaiting("needs review", "approval", "run-1");
    });

    expect(result.current.info).toMatchObject({
      phase: "waiting_human",
      reason: "needs review",
      trigger: "approval",
      runId: "run-1",
      remainingSeconds: TAKEOVER_TIMEOUT,
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(result.current.info.remainingSeconds).toBe(TAKEOVER_TIMEOUT - 1);
  });

  it("cancels with timeout reason and fires onTimeout when countdown ends", () => {
    const onTimeout = vi.fn();
    const { result } = renderHook(() => useTakeoverState(onTimeout));

    act(() => {
      result.current.enterWaiting("reason", "trigger", "run-1");
    });

    act(() => {
      vi.advanceTimersByTime(TAKEOVER_TIMEOUT * 1000);
    });

    expect(result.current.info.phase).toBe("cancelled");
    expect(result.current.info.reason).toContain("Timed out");
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  it("enterHumanControl stops the countdown", () => {
    const onTimeout = vi.fn();
    const { result } = renderHook(() => useTakeoverState(onTimeout));

    act(() => {
      result.current.enterWaiting("reason", "trigger", "run-1");
      vi.advanceTimersByTime(1000);
      result.current.enterHumanControl();
    });

    const remainingAtHandover = result.current.info.remainingSeconds;
    expect(result.current.info.phase).toBe("human_control");

    act(() => {
      vi.advanceTimersByTime(TAKEOVER_TIMEOUT * 1000);
    });

    expect(result.current.info.remainingSeconds).toBe(remainingAtHandover);
    expect(result.current.info.phase).toBe("human_control");
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it("enterResuming transitions to resuming phase", () => {
    const { result } = renderHook(() => useTakeoverState());

    act(() => {
      result.current.enterWaiting("reason", "trigger", "run-1");
      result.current.enterResuming();
    });

    expect(result.current.info.phase).toBe("resuming");
  });

  it("reset restores initial state and stops countdown", () => {
    const onTimeout = vi.fn();
    const { result } = renderHook(() => useTakeoverState(onTimeout));

    act(() => {
      result.current.enterWaiting("reason", "trigger", "run-1");
      result.current.reset();
    });

    expect(result.current.info).toMatchObject({
      phase: "none",
      reason: "",
      trigger: "",
      remainingSeconds: TAKEOVER_TIMEOUT,
      runId: "",
    });

    act(() => {
      vi.advanceTimersByTime(TAKEOVER_TIMEOUT * 1000);
    });

    expect(onTimeout).not.toHaveBeenCalled();
  });

  it("clears the timer on unmount", () => {
    const onTimeout = vi.fn();
    const { result, unmount } = renderHook(() => useTakeoverState(onTimeout));

    act(() => {
      result.current.enterWaiting("reason", "trigger", "run-1");
      unmount();
    });

    act(() => {
      vi.advanceTimersByTime(TAKEOVER_TIMEOUT * 1000);
    });

    expect(onTimeout).not.toHaveBeenCalled();
  });
});
