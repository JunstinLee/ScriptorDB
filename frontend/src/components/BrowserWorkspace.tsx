import { Monitor, Loader2, X, ImageIcon } from "lucide-react";
import type { BrowserState, BrowserActionEvent, HumanTakeoverRequestEvent, BrowserProfileItem, CookieInfo } from "../types";
import { getScreenshotUrl } from "../api/browser";
import { ActionStream } from "./ActionStream";
import { BrowserSessionInfo } from "./BrowserSessionInfo";
import { HumanTakeoverPanel } from "./HumanTakeoverPanel";

interface BrowserWorkspaceProps {
  state: BrowserState | null;
  loading: boolean;
  error: string | null;
  actions?: BrowserActionEvent[];
  isRunning?: boolean;
  latestAction?: BrowserActionEvent | null;
  takeoverEvent?: HumanTakeoverRequestEvent | null;
  onTakeoverComplete?: (result: string) => void;
  onTakeoverCancel?: () => void;
  onClearActions?: () => void;
  onScreenshotRefresh?: () => void;
  profiles?: BrowserProfileItem[];
  cookies?: CookieInfo[];
  cookiesLoading?: boolean;
  onLoadProfile?: (name: string) => void;
}

function BrowserViewport({
  state,
  loading,
  latestAction,
  takeoverActive,
  onImageClick,
}: {
  state: BrowserState | null;
  loading: boolean;
  latestAction?: BrowserActionEvent | null;
  takeoverActive: boolean;
  onImageClick?: () => void;
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
    <div className="flex flex-1 flex-col gap-3 p-4 min-w-0">
      <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface [transform:translateZ(0)]">
        {state.screenshot_available ? (
          <img
            src={getScreenshotUrl()}
            alt={state.title ?? "页面截图"}
            className="h-full w-full object-contain"
            style={{ cursor: takeoverActive ? "crosshair" : "default" }}
            onClick={() => onImageClick?.()}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <ImageIcon className="size-12 text-muted" />
          </div>
        )}

        {latestAction?.coords && (
          <div
            className="absolute border-2 border-red-400/60 rounded pointer-events-none"
            style={{
              left: latestAction.coords.x,
              top: latestAction.coords.y,
              width: latestAction.coords.width,
              height: latestAction.coords.height,
            }}
          />
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
  actions,
  isRunning,
  latestAction,
  takeoverEvent,
  onTakeoverComplete,
  onTakeoverCancel,
  onClearActions,
  onScreenshotRefresh,
  profiles,
  cookies,
  cookiesLoading,
  onLoadProfile,
}: BrowserWorkspaceProps) {
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

  if (takeoverEvent) {
    return (
      <div className="flex flex-1 min-h-0 min-w-0">
        <HumanTakeoverPanel
          event={takeoverEvent}
          onComplete={onTakeoverComplete ?? (() => {})}
          onCancel={onTakeoverCancel ?? (() => {})}
          screenshotSrc={getScreenshotUrl()}
          onScreenshotRefresh={onScreenshotRefresh ?? (() => {})}
          actions={actions ?? []}
          onClearActions={onClearActions ?? (() => {})}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 min-w-0">
      {state?.launched && (
        <BrowserSessionInfo
          profiles={profiles ?? []}
          cookies={cookies ?? []}
          cookiesLoading={cookiesLoading ?? false}
          browserLaunched={state.launched}
          currentUrl={state?.url ?? ""}
          onLoadProfile={onLoadProfile}
        />
      )}
      <div className="flex flex-1 min-h-0 min-w-0">
        <BrowserViewport state={state} loading={loading} latestAction={latestAction} takeoverActive={false} />
        <ActionStream events={actions ?? []} isRunning={isRunning ?? false} />
      </div>
    </div>
  );
}
