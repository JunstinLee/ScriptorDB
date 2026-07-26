import { Loader2, Check, X, ChevronRight } from "lucide-react";
import type { BrowserState } from "../types";

function safeHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

interface BrowserContextCardProps {
  state: BrowserState | null;
  loading: boolean;
  onViewInMain: () => void;
}

export function BrowserContextCard({ state, loading, onViewInMain }: BrowserContextCardProps) {
  if (!state?.launched) return null;

  const recentActions = state.actions.slice(-3).reverse();

  return (
    <div className="border-b border-grid px-3 py-3">
      <div className="rounded-lg border border-grid bg-surface p-3">
        <div className="mb-2 flex items-center gap-2">
          {loading ? (
            <Loader2 className="size-2.5 animate-spin text-accent" />
          ) : (
            <span className="size-2.5 rounded-full bg-success" />
          )}
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Browser Context
          </span>
        </div>

        {state.url ? (
          <p className="mb-2 truncate font-mono text-xs text-foreground"
             title={state.url}>
            {safeHostname(state.url)}
          </p>
        ) : (
          <p className="mb-2 text-xs text-muted">等待导航...</p>
        )}

        {recentActions.length > 0 && (
          <div className="mb-2 flex flex-col gap-1">
            {recentActions.map((action, i) => (
              <div key={i} className="flex items-center gap-1.5">
                {action.success ? (
                  <Check className="size-3 shrink-0 text-success" />
                ) : (
                  <X className="size-3 shrink-0 text-danger" />
                )}
                <span className="truncate text-[11px] text-muted">
                  {action.tool}
                </span>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={onViewInMain}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[11px] text-accent hover:bg-accent/10 transition-colors"
        >
          <span>在主区域查看</span>
          <ChevronRight className="size-3" />
        </button>
      </div>
    </div>
  );
}
