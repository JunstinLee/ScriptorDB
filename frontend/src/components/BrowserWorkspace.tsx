import { Loader2, X, ImageIcon, Monitor } from "lucide-react";
import type { BrowserState, BrowserActionEvent, BrowserProfileItem, CookieInfo, FilterSchema, LoginFormPayload } from "../types";
import { getScreenshotUrl } from "../api/browser";
import { BrowserSessionInfo } from "./BrowserSessionInfo";
import { BrowserViewportStream } from "./BrowserViewportStream";
import { BrowserStatusBar } from "./BrowserStatusBar";
import { FilterPanel } from "./FilterPanel";
import { HumanTakeoverDrawer } from "./HumanTakeoverPanel";
import type { TakeoverInfo } from "../hooks/useTakeoverState";

interface BrowserWorkspaceProps {
  state: BrowserState | null;
  loading: boolean;
  error: string | null;
  actions?: BrowserActionEvent[];
  isRunning?: boolean;
  takeoverInfo: TakeoverInfo;
  onTakeoverComplete?: (result: string) => void;
  onTakeoverCancel?: () => void;
  onEnterHumanControl?: () => void;
  onShowTakeoverWindow?: () => void;
  onClearActions?: () => void;
  profiles?: BrowserProfileItem[];
  cookies?: CookieInfo[];
  cookiesLoading?: boolean;
  onLoadProfile?: (name: string) => void;
  sessionId?: string;
  filterSchema?: FilterSchema | null;
  loginForm?: LoginFormPayload | null;
  onFiltersApplied?: () => void;
  onCloseBrowser?: () => void;
}

function BrowserViewport({
  state,
  loading,
}: {
  state: BrowserState | null;
  loading: boolean;
}) {
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
          Waiting for the agent to launch the browser...
        </p>
      </div>
    );
  }

  if (!state.url) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <Loader2 className="size-6 animate-spin text-accent" />
        <p className="text-sm text-muted">Launching browser...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3 p-4 min-w-0">
      <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface [transform:translateZ(0)]">
        {state.screenshot_available ? (
          <img
            src={getScreenshotUrl()}
            alt={state.title ?? "Page screenshot"}
            className="h-full w-full object-contain"
            style={{ cursor: "default" }}
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

export function BrowserWorkspace({
  state,
  loading,
  error,
  takeoverInfo,
  onTakeoverComplete,
  onTakeoverCancel,
  onEnterHumanControl,
  onShowTakeoverWindow,
  profiles,
  cookies,
  cookiesLoading,
  onLoadProfile,
  sessionId,
  actions,
  isRunning,
  filterSchema,
  loginForm,
  onFiltersApplied,
  onCloseBrowser,
}: BrowserWorkspaceProps) {
  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3 rounded-xl border border-danger/30 bg-danger/5 px-8 py-6">
          <X className="size-6 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <p className="text-xs text-muted">Check that the backend is running</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 min-w-0">
      <BrowserStatusBar
        phase={takeoverInfo.phase}
        reason={takeoverInfo.reason}
        trigger={takeoverInfo.trigger}
        remainingSeconds={takeoverInfo.remainingSeconds}
        browserRunning={!!state?.launched}
        idleCloseActive={state?.idle_close_active ?? false}
        idleCloseRemaining={state?.idle_close_remaining ?? 0}
        onCloseBrowser={onCloseBrowser ?? (() => {})}
      />

      {state?.launched && (
        <BrowserSessionInfo
          profiles={profiles ?? []}
          cookies={cookies ?? []}
          cookiesLoading={cookiesLoading ?? false}
          browserLaunched={state.launched}
          currentUrl={state?.url ?? ""}
          onLoadProfile={onLoadProfile}
          actions={actions}
          isRunning={isRunning}
        />
      )}

      {state?.launched && (
        <FilterPanel
          schema={filterSchema ?? null}
          isRunning={isRunning ?? false}
          sessionId={sessionId ?? ""}
          onApplied={onFiltersApplied}
        />
      )}

      <div className="flex flex-1 min-h-0 min-w-0">
        {state?.launched ? (
          <BrowserViewportStream
            takeoverActive={takeoverInfo.phase === "human_control"}
          />
        ) : (
          <BrowserViewport state={state} loading={loading} />
        )}
      </div>

      {(takeoverInfo.phase === "waiting_human" ||
        takeoverInfo.phase === "human_control" ||
        takeoverInfo.phase === "resuming") && (
        <HumanTakeoverDrawer
          phase={takeoverInfo.phase}
          reason={takeoverInfo.reason}
          currentUrl={state?.url ?? ""}
          trigger={takeoverInfo.trigger}
          remainingSeconds={takeoverInfo.remainingSeconds}
          loginForm={loginForm}
          onEnterControl={onEnterHumanControl ?? (() => {})}
          onCancel={onTakeoverCancel ?? (() => {})}
          onComplete={onTakeoverComplete ?? (() => {})}
          onShowWindow={onShowTakeoverWindow ?? (() => {})}
          runId={takeoverInfo.runId}
          sessionId={sessionId ?? ""}
        />
      )}
    </div>
  );
}
