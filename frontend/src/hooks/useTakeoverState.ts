import { useState, useRef, useCallback, useEffect } from "react";

export type TakeoverPhase =
  | "none"
  | "waiting_human"
  | "human_control"
  | "resuming"
  | "cancelled";

export interface TakeoverInfo {
  phase: TakeoverPhase;
  reason: string;
  trigger: string;
  remainingSeconds: number;
  runId: string;
}

const TAKEOVER_TIMEOUT = 150;

export function useTakeoverState(onTimeout?: () => void) {
  const [info, setInfo] = useState<TakeoverInfo>({
    phase: "none",
    reason: "",
    trigger: "",
    remainingSeconds: TAKEOVER_TIMEOUT,
    runId: "",
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startCountdown = useCallback(() => {
    clearTimer();
    startTimeRef.current = Date.now();
    setInfo((prev) => ({ ...prev, remainingSeconds: TAKEOVER_TIMEOUT }));

    timerRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      const remaining = Math.max(0, Math.ceil(TAKEOVER_TIMEOUT - elapsed));
      setInfo((prev) => ({ ...prev, remainingSeconds: remaining }));

      if (remaining <= 0) {
        clearTimer();
        setInfo((prev) => ({
          ...prev,
          phase: "cancelled",
          reason: `Timed out: no user response in ${TAKEOVER_TIMEOUT}s`,
        }));
        onTimeout?.();
      }
    }, 1000);
  }, [clearTimer]);

  const enterWaiting = useCallback(
    (reason: string, trigger: string, runId: string) => {
      setInfo({
        phase: "waiting_human",
        reason,
        trigger,
        remainingSeconds: TAKEOVER_TIMEOUT,
        runId,
      });
      startCountdown();
    },
    [startCountdown]
  );

  const enterHumanControl = useCallback(() => {
    clearTimer();
    setInfo((prev) => ({ ...prev, phase: "human_control" }));
  }, [clearTimer]);

  const enterResuming = useCallback(() => {
    clearTimer();
    setInfo((prev) => ({ ...prev, phase: "resuming" }));
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setInfo({
      phase: "none",
      reason: "",
      trigger: "",
      remainingSeconds: TAKEOVER_TIMEOUT,
      runId: "",
    });
  }, [clearTimer]);

  useEffect(() => {
    return () => clearTimer();
  }, [clearTimer]);

  return {
    info,
    enterWaiting,
    enterHumanControl,
    enterResuming,
    reset,
  };
}
