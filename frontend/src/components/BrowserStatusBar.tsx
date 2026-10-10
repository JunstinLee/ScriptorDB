import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import type { TakeoverPhase } from "../hooks/useTakeoverState";

interface BrowserStatusBarProps {
  phase: TakeoverPhase;
  reason: string;
  trigger: string;
  remainingSeconds: number;
  browserRunning: boolean;
  /** 任务结束后的自动关闭倒计时是否进行中 */
  idleCloseActive: boolean;
  /** 服务端下发的剩余秒数（每次轮询校准） */
  idleCloseRemaining: number;
  onCloseBrowser: () => void;
}

const PHASE_CONFIG: Record<
  TakeoverPhase,
  { color: string; labelKey: string; animate?: boolean }
> = {
  none:           { color: "bg-green-500",   labelKey: "browser.phase.agent_running" },
  waiting_human:  { color: "bg-amber-500",   labelKey: "browser.phase.awaiting_user", animate: true },
  human_control:  { color: "bg-blue-500",    labelKey: "browser.phase.human_control" },
  resuming:       { color: "bg-emerald-500", labelKey: "browser.phase.resuming",       animate: true },
  cancelled:      { color: "bg-gray-400",    labelKey: "browser.phase.cancelled" },
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
  idleCloseActive,
  idleCloseRemaining,
  onCloseBrowser,
}: BrowserStatusBarProps) {
  const { t } = useTranslation();
  const config = PHASE_CONFIG[phase];

  // 以轮询下发的服务端值为基准，本地每秒递减展示
  const [displayRemaining, setDisplayRemaining] = useState(idleCloseRemaining);

  useEffect(() => {
    setDisplayRemaining(idleCloseRemaining);
  }, [idleCloseRemaining]);

  useEffect(() => {
    if (!idleCloseActive) return;
    const timer = setInterval(() => {
      setDisplayRemaining((d) => Math.max(0, d - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [idleCloseActive]);

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-grid bg-surface/50 min-w-0">
      <div
        className={`size-2.5 rounded-full ${config.color} ${
          config.animate ? "animate-pulse" : ""
        }`}
      />

      <span className="text-sm font-semibold whitespace-nowrap">
        {t(config.labelKey)}
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

      {idleCloseActive && browserRunning ? (
        <div className="ml-auto flex items-center gap-2 whitespace-nowrap">
          <span className="text-[11px] font-mono text-muted">
            {t("browser.auto_close", { time: formatTime(displayRemaining) })}
          </span>
          <button
            type="button"
            onClick={onCloseBrowser}
            className="flex items-center gap-1 rounded-lg border border-grid px-2 py-1 text-[11px] text-muted transition-colors hover:bg-surface hover:text-danger"
            title={t("browser.close_now")}
          >
            <X className="size-3" />
            {t("browser.close")}
          </button>
        </div>
      ) : (
        !browserRunning && (
          <span className="text-xs text-muted ml-auto">{t("browser.not_running")}</span>
        )
      )}
    </div>
  );
}
