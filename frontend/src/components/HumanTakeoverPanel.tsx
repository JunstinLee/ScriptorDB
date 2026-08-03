import { useState } from "react";
import { AlertTriangle, Monitor } from "lucide-react";
import type { TakeoverPhase } from "../hooks/useTakeoverState";

interface HumanTakeoverDrawerProps {
  phase: TakeoverPhase;
  reason: string;
  currentUrl: string;
  trigger: string;
  remainingSeconds: number;
  onEnterControl: () => void;
  onCancel: () => void;
  onComplete: (result: string) => void;
  onShowWindow: () => void;
  runId: string;
  sessionId: string;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function HumanTakeoverDrawer({
  phase,
  reason,
  currentUrl,
  remainingSeconds,
  onEnterControl,
  onCancel,
  onComplete,
  onShowWindow,
}: HumanTakeoverDrawerProps) {
  const [resultText, setResultText] = useState("");

  if (phase === "resuming") {
    return (
      <div className="border-t border-grid bg-surface px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-muted">
          <div className="size-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Agent 恢复中...
        </div>
      </div>
    );
  }

  if (phase === "waiting_human") {
    return (
      <div className="border-t border-amber-500/40 bg-amber-500/5 px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <AlertTriangle className="size-5 shrink-0 text-amber-500" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                Agent 已暂停 — 需要人工操作
              </p>
              <p className="text-xs text-amber-600/80 dark:text-amber-300/70 truncate mt-0.5">
                {reason}
              </p>
              <p className="text-[11px] text-muted truncate font-mono mt-0.5">
                {currentUrl}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted font-mono">
              {formatTime(remainingSeconds)}
            </span>
            <button
              onClick={onCancel}
              className="rounded-lg border border-grid px-3 py-1.5 text-xs text-muted hover:bg-surface"
            >
              忽略
            </button>
            <button
              onClick={onEnterControl}
              className="rounded-lg bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent/90"
            >
              接管
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (phase === "human_control") {
    return (
      <div className="border-t border-blue-500/40 bg-blue-500/5 px-4 py-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="size-2 rounded-full bg-blue-500" />
            <span className="text-sm font-semibold text-blue-700 dark:text-blue-400">
              Chrome 窗口已打开 — 请在窗口中直接操作
            </span>
          </div>
        </div>

        <div className="flex gap-4 text-xs text-muted mb-3">
          <span className="flex items-center gap-1">
            <Monitor className="size-3" /> 视频画面为只读预览，请在真实 Chrome 窗口中操作
          </span>
        </div>

        <div className="space-y-2">
          <textarea
            id="takeover-result"
            value={resultText}
            onChange={(e) => setResultText(e.target.value)}
            placeholder="描述你做了什么操作（可选）..."
            rows={2}
            className="w-full resize-none rounded-lg border border-grid bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <div className="flex justify-between gap-2">
            <button
              onClick={onShowWindow}
              className="rounded-lg border border-grid px-3 py-1.5 text-xs text-muted hover:bg-surface"
            >
              显示 Chrome 窗口
            </button>
            <div className="flex gap-2">
              <button
                onClick={onCancel}
                className="rounded-lg border border-grid px-4 py-1.5 text-xs text-muted hover:bg-surface"
              >
                取消接管
              </button>
              <button
                onClick={() => onComplete(resultText || "用户完成操作")}
                className="rounded-lg bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent/90"
              >
                完成并恢复 Agent
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
