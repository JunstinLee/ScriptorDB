import type { TakeoverPhase } from "../hooks/useTakeoverState";

interface BrowserStatusBarProps {
  phase: TakeoverPhase;
  reason: string;
  trigger: string;
  remainingSeconds: number;
  browserRunning: boolean;
}

const PHASE_CONFIG: Record<
  TakeoverPhase,
  { color: string; label: string; animate?: boolean }
> = {
  none:           { color: "bg-green-500",   label: "Agent running" },
  waiting_human:  { color: "bg-amber-500",   label: "Awaiting user action", animate: true },
  human_control:  { color: "bg-blue-500",    label: "Human control" },
  resuming:       { color: "bg-emerald-500", label: "Resuming",       animate: true },
  cancelled:      { color: "bg-gray-400",    label: "Cancelled" },
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function BrowserStatusBar({
  phase,
  reason,
  trigger,
  remainingSeconds,
  browserRunning,
}: BrowserStatusBarProps) {
  const config = PHASE_CONFIG[phase];

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-grid bg-surface/50 min-w-0">
      <div
        className={`size-2.5 rounded-full ${config.color} ${
          config.animate ? "animate-pulse" : ""
        }`}
      />

      <span className="text-sm font-semibold whitespace-nowrap">
        {config.label}
      </span>

      {reason && (
        <span className="text-xs text-muted truncate flex-1 min-w-0">
          — {reason}
        </span>
      )}

      {trigger && phase !== "none" && (
        <span className="text-[11px] px-1.5 py-0.5 rounded font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300">
          {trigger}
        </span>
      )}

      {phase === "waiting_human" && (
        <span className="text-[11px] font-mono text-muted whitespace-nowrap">
          {formatTime(remainingSeconds)}
        </span>
      )}

      {!browserRunning && (
        <span className="text-xs text-muted ml-auto">Browser not running</span>
      )}
    </div>
  );
}
