import { useEffect, useRef } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { BrowserActionEvent } from "../types";

interface ActionStreamProps {
  events: BrowserActionEvent[];
  isRunning: boolean;
}

const TOOL_LABELS: Record<string, (detail: string) => string> = {
  browser_navigate: (d) => `Open ${extractUrl(d)}`,
  browser_click: (d) => `Click ${extractSelector(d)}`,
  browser_fill: (d) => {
    const s = extractSelector(d);
    return `Fill ${s}`;
  },
  browser_wait_for_selector: (d) => `Wait ${extractSelector(d)}`,
  browser_scroll: (d) => {
    const px = extractPixels(d);
    return px > 0 ? `Scroll down ${px}px` : `Scroll up ${Math.abs(px)}px`;
  },
  browser_screenshot: () => "Screenshot saved",
  browser_press_key: (d) => `Press ${extractKey(d)}`,
  browser_get_cookies: () => "Cookies saved",
  browser_evaluate: () => "Evaluate JavaScript",
  browser_query: (d) => `Query ${extractSelector(d)}`,
  browser_launch: () => "Launch browser",
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

function extractKey(detail: string): string {
  return detail || "key";
}

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return "";
  }
}

function getLabel(tool: string, detail: string): string {
  const fn = TOOL_LABELS[tool];
  return fn ? fn(detail) : defaultLabel(tool, detail);
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
          {getLabel(event.tool, event.detail)}
        </p>
        <p className="mt-0.5 text-[10px] text-muted/60">
          {formatTime(event.timestamp)}
        </p>
      </div>

      <span className="shrink-0 text-[9px] text-muted/50">
        {event.tool}
      </span>
    </div>
  );
}

export function ActionStream({ events, isRunning }: ActionStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="flex w-[38%] shrink-0 flex-col items-center justify-center border-l border-grid px-4 py-8">
        <p className="text-xs italic text-muted">Waiting for agent actions...</p>
      </div>
    );
  }

  const reversed = [...events].reverse();

  return (
    <div className="flex w-[38%] shrink-0 flex-col border-l border-grid">
      <div className="shrink-0 border-b border-grid px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
          Agent Actions
        </h3>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-1 py-2">
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
    </div>
  );
}
