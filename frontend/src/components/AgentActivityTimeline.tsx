import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { BrowserActionEvent } from "../types";

interface AgentActivityTimelineProps {
  events: BrowserActionEvent[];
  isRunning: boolean;
}

type Translate = (key: string, params?: Record<string, string | number>) => string;

const TOOL_LABELS: Record<string, (detail: string, t: Translate) => string> = {
  browser_navigate: (d, t) => t("browser.action.open", { url: extractUrl(d) }),
  browser_click: (d, t) => t("browser.action.click", { selector: extractSelector(d) }),
  browser_fill: (d, t) => {
    const s = extractSelector(d);
    return t("browser.action.fill", { selector: s });
  },
  browser_wait_for_selector: (d, t) => t("browser.action.wait", { selector: extractSelector(d) }),
  browser_scroll: (d, t) => {
    const px = extractPixels(d);
    return px > 0
      ? t("browser.action.scroll_down", { px })
      : t("browser.action.scroll_up", { px: Math.abs(px) });
  },
  browser_press_key: (d, t) => t("browser.action.press", { key: extractKey(d, t) }),
  browser_get_cookies: (_d, t) => t("browser.action.cookies"),
  browser_evaluate: (_d, t) => t("browser.action.evaluate"),
  browser_query: (d, t) => t("browser.action.query", { selector: extractSelector(d) }),
  browser_launch: (_d, t) => t("browser.action.launch"),
};

function defaultLabel(tool: string, detail: string): string {
  return detail || tool;
}

function extractUrl(detail: string): string {
  try {
    const u = new URL(detail);
    return u.hostname + (u.pathname.length > 1 ? u.pathname : "");
  } catch {
    try {
      const u = new URL(`https://${detail}`);
      return u.hostname + (u.pathname.length > 1 ? u.pathname : "");
    } catch {
      return detail;
    }
  }
}

function extractSelector(detail: string): string {
  const trimmed = detail.trim();
  if (!trimmed || trimmed.length > 60) {
    return trimmed.slice(0, 60) + "…";
  }
  return trimmed;
}

function extractPixels(detail: string): number {
  const n = parseInt(detail, 10);
  return isNaN(n) ? 0 : n;
}

function extractKey(detail: string, t: Translate): string {
  return detail || t("browser.action_key_fallback");
}

function formatTime(isoString: string, locale: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString(locale, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return "";
  }
}

function getLabel(tool: string, detail: string, t: Translate): string {
  const fn = TOOL_LABELS[tool];
  return fn ? fn(detail, t) : defaultLabel(tool, detail);
}

function ActionRow({
  event,
  isLatest,
  isRunning,
}: {
  event: BrowserActionEvent;
  isLatest: boolean;
  isRunning: boolean;
}) {
  const { t, i18n } = useTranslation();
  const isInProgress = isLatest && isRunning;

  return (
    <div className="flex items-start gap-2 rounded-md px-3 py-2 hover:bg-default/30">
      {isInProgress ? (
        <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-amber-400" />
      ) : event.success ? (
        <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-green-400" />
      ) : (
        <XCircle className="mt-0.5 size-3.5 shrink-0 text-red-400" />
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate text-xs text-foreground">
          {getLabel(event.tool, event.detail, t)}
        </p>
        <p className="mt-0.5 text-[10px] text-muted/60">
          {formatTime(event.timestamp, i18n.language)}
        </p>
      </div>

      <span className="shrink-0 text-[9px] text-muted/50">
        {event.tool}
      </span>
    </div>
  );
}

export function AgentActivityTimeline({ events, isRunning }: AgentActivityTimelineProps) {
  const { t } = useTranslation();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="px-3 py-4 text-center">
        <p className="text-xs italic text-muted">{t("browser.waiting_actions")}</p>
      </div>
    );
  }

  const reversed = [...events].reverse();

  return (
    <div className="max-h-72 min-w-80 overflow-y-auto px-1 py-1">
      {reversed.map((evt, i) => (
        <ActionRow
          key={`${evt.tool}-${evt.timestamp}-${i}`}
          event={evt}
          isLatest={i === 0}
          isRunning={isRunning}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
