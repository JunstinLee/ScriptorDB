import { Monitor, Loader2, Check, X, ImageIcon } from "lucide-react";
import type { BrowserState, BrowserAction, BrowserHistoryEntry } from "../types";
import { getScreenshotUrl } from "../api/browser";

interface BrowserWorkspaceProps {
  state: BrowserState | null;
  loading: boolean;
  error: string | null;
}

/** ISO 8601 时间字符串 → 相对时间文本（"刚刚"、"3秒前"、"1分前"） */
function formatRelativeTime(isoString: string): string {
  const then = new Date(isoString).getTime();
  const now = Date.now();
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 5) return "刚刚";
  if (seconds < 60) return `${seconds}秒前`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分前`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;

  return new Date(isoString).toLocaleDateString("zh-CN");
}

function ActionEntry({ action, isLatest }: { action: BrowserAction; isLatest: boolean }) {
  return (
    <div className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-default/30">
      {isLatest ? (
        <Loader2 className="mt-0.5 size-3 shrink-0 animate-spin text-accent" />
      ) : action.success ? (
        <Check className="mt-0.5 size-3 shrink-0 text-success" />
      ) : (
        <X className="mt-0.5 size-3 shrink-0 text-danger" />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="shrink-0 rounded bg-default/50 px-1.5 text-[11px] font-medium text-foreground/80">
            {action.tool}
          </span>
          <span className="shrink-0 text-[11px] text-muted">
            {formatRelativeTime(action.timestamp)}
          </span>
        </div>
        <p className="mt-0.5 truncate text-xs text-muted">
          {action.detail}
        </p>
      </div>
    </div>
  );
}

function HistoryEntry({ entry, isCurrent }: { entry: BrowserHistoryEntry; isCurrent: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded px-2 py-1 hover:bg-default/30">
      <span
        className={`size-2 shrink-0 rounded-full ${
          isCurrent ? "bg-accent" : "border border-muted bg-transparent"
        }`}
      />

      <div className="min-w-0 flex-1">
        <p className="truncate text-xs text-foreground">
          {safeUrlDisplay(entry.url)}
        </p>
        <p className="text-[10px] text-muted">
          {formatRelativeTime(entry.timestamp)}
        </p>
      </div>
    </div>
  );
}

function safeUrlDisplay(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname.length > 1 ? u.pathname : "";
    return u.hostname + path;
  } catch {
    return url;
  }
}

function BrowserViewport({ state, loading }: { state: BrowserState | null; loading: boolean }) {
  if (!state?.launched) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6">
        <div className="flex h-40 w-64 items-center justify-center rounded-xl border-2 border-dashed border-grid bg-surface/50">
          <div className="flex flex-col items-center gap-2">
            <Monitor className="size-8 text-muted" />
            <span className="font-mono text-xs text-muted">
              ░░░░░░░░░░░░░░░░░░░░
            </span>
          </div>
        </div>
        <p className="text-center text-sm text-muted">
          等待智能体启动浏览器...
        </p>
      </div>
    );
  }

  if (!state.url) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <Loader2 className="size-6 animate-spin text-accent" />
        <p className="text-sm text-muted">浏览器启动中...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3 p-4">
      <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface">
        {state.screenshot_available ? (
          <img
            src={getScreenshotUrl()}
            alt={state.title ?? "页面截图"}
            className="h-full w-full object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <ImageIcon className="size-12 text-muted" />
          </div>
        )}

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <Loader2 className="size-6 animate-spin text-accent" />
          </div>
        )}
      </div>

      {state.title && (
        <p className="truncate text-[13px] font-medium text-foreground">
          {state.title}
        </p>
      )}

      <div className="rounded-lg border-l-2 border-accent bg-[#EBE8E1] px-3 py-2 dark:bg-[#1E2028]">
        <p className="truncate font-mono text-sm text-foreground">
          ▸ {state.url}
        </p>
      </div>
    </div>
  );
}

function ExecutionTimeline({ state, loading }: { state: BrowserState | null; loading: boolean }) {
  const actions = state?.actions ?? [];
  const history = state?.history ?? [];

  const reversedActions = [...actions].reverse();
  const reversedHistory = [...history].reverse();

  const isCurrentUrl = (url: string) => state?.url === url;

  return (
    <div className="flex w-[38%] min-w-0 shrink-0 flex-col gap-4 overflow-y-auto border-l border-grid px-4 py-3">
      <div>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
          执行日志
        </h3>

        {reversedActions.length === 0 ? (
          <p className="text-xs text-muted">暂无操作记录</p>
        ) : (
          <div className="flex flex-col gap-2">
            {reversedActions.map((action, i) => (
              <ActionEntry
                key={`${action.tool}-${action.timestamp}-${i}`}
                action={action}
                isLatest={i === 0 && loading}
              />
            ))}
          </div>
        )}
      </div>

      {reversedHistory.length > 0 && (
        <div>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            页面历史
          </h3>

          <div className="flex flex-col gap-1.5">
            {reversedHistory.map((entry, i) => (
              <HistoryEntry
                key={`${entry.url}-${entry.timestamp}-${i}`}
                entry={entry}
                isCurrent={isCurrentUrl(entry.url)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function BrowserWorkspace({ state, loading, error }: BrowserWorkspaceProps) {
  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3 rounded-xl border border-danger/30 bg-danger/5 px-8 py-6">
          <X className="size-6 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <p className="text-xs text-muted">检查后端服务是否正常运行</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 min-h-0">
      <BrowserViewport state={state} loading={loading} />
      <ExecutionTimeline state={state} loading={loading} />
    </div>
  );
}
