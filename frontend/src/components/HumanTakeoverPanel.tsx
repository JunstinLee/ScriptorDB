import { useState } from "react";
import { useTranslation } from "react-i18next";
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

/** 是否 MFA/验证码类接管（trigger=mfa 或文案含验证码关键词） */
function isOtpTrigger(trigger: string, reason: string): boolean {
  const t = `${trigger} ${reason}`.toLowerCase();
  return (
    trigger.toLowerCase() === "mfa" ||
    t.includes("verification code") ||
    t.includes("验证码") ||
    t.includes("otp") ||
    t.includes("one-time-code")
  );
}

export function HumanTakeoverDrawer({
  phase,
  reason,
  trigger,
  currentUrl,
  remainingSeconds,
  onEnterControl,
  onCancel,
  onComplete,
  onShowWindow,
}: HumanTakeoverDrawerProps) {
  const { t } = useTranslation();
  const [resultText, setResultText] = useState("");

  if (phase === "resuming") {
    return (
      <div className="border-t border-grid bg-surface px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-muted">
          <div className="size-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          {t("takeover.resuming")}
        </div>
      </div>
    );
  }

  const otpGuidance = isOtpTrigger(trigger, reason);

  if (phase === "waiting_human") {
    return (
      <div className="border-t border-amber-500/40 bg-amber-500/5 px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <AlertTriangle className="size-5 shrink-0 text-amber-500" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                {otpGuidance
                  ? t("takeover.otp_title")
                  : t("takeover.paused_title")}
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
              {t("takeover.dismiss")}
            </button>
            <button
              onClick={onEnterControl}
              className="rounded-lg bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent/90"
            >
              {t("takeover.take_over")}
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
              {otpGuidance
                ? t("takeover.otp_control_title")
                : t("takeover.control_title")}
            </span>
          </div>
        </div>

        <div className="flex gap-4 text-xs text-muted mb-3">
          <span className="flex items-center gap-1">
            <Monitor className="size-3" /> {t("takeover.read_only_hint")}
          </span>
        </div>

        <div className="space-y-2">
          <textarea
            id="takeover-result"
            value={resultText}
            onChange={(e) => setResultText(e.target.value)}
            placeholder={t("takeover.result_placeholder")}
            rows={2}
            className="w-full resize-none rounded-lg border border-grid bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <div className="flex justify-between gap-2">
            <button
              onClick={onShowWindow}
              className="rounded-lg border border-grid px-3 py-1.5 text-xs text-muted hover:bg-surface"
            >
              {t("takeover.show_window")}
            </button>
            <div className="flex gap-2">
              <button
                onClick={onCancel}
                className="rounded-lg border border-grid px-4 py-1.5 text-xs text-muted hover:bg-surface"
              >
                {t("takeover.cancel")}
              </button>
              <button
                onClick={() => onComplete(resultText || t("takeover.default_result"))}
                className="rounded-lg bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent/90"
              >
                {t("takeover.finish")}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
