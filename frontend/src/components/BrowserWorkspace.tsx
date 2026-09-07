import { useState } from "react";
import { Loader2, X, ImageIcon, Monitor } from "lucide-react";
import type {
  BrowserState,
  BrowserActionEvent,
  BrowserProfileItem,
  CookieInfo,
  FilterSchema,
  LoginFieldInfo,
  LoginFlowStatus,
  LoginFormPayload,
} from "../types";
import { getScreenshotUrl } from "../api/browser";
import { BrowserSessionInfo } from "./BrowserSessionInfo";
import { BrowserViewportStream } from "./BrowserViewportStream";
import { BrowserStatusBar } from "./BrowserStatusBar";
import { FilterPanel } from "./FilterPanel";
import { HumanTakeoverDrawer } from "./HumanTakeoverPanel";
import { OtpGuidanceNotice } from "./OtpGuidanceNotice";
import { LoginStatusPanel } from "./LoginStatusPanel";
import { CredentialSetupPanel } from "./CredentialSetupPanel";
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
  /** 最近一次 login_flow_status（旁路状态；autofill 进度/otp 引导） */
  loginFlowStatus?: LoginFlowStatus | null;
  /** 站点是否已配置凭证（useLoginAutofillState 派生；null=未知） */
  credentialConfigured?: boolean | null;
  credentialSite?: string;
  credentialUrl?: string;
  fieldCandidates?: LoginFieldInfo[];
  /** 保存/删除后本地翻转 configured */
  onCredentialStatusChange?: (configured: boolean) => void;
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

/** 登录状态区（03 唯一挂载点）：otp 引导 / 进度面板 / 凭证采集互斥布局。 */
function LoginArea({
  loginFlowStatus,
  configured,
  reconfigureOpen,
  site,
  url,
  fieldCandidates,
  onConfiguredChange,
  onOpenReconfigure,
  onCloseReconfigure,
}: {
  loginFlowStatus: LoginFlowStatus | null;
  configured: boolean;
  reconfigureOpen: boolean;
  site: string;
  url: string;
  fieldCandidates: LoginFieldInfo[];
  onConfiguredChange: (configured: boolean) => void;
  onOpenReconfigure: () => void;
  onCloseReconfigure: () => void;
}) {
  const status = loginFlowStatus;
  const manualOtp = status?.manual_otp_guided === true;
  const configuredEff = configured || reconfigureOpen;

  return (
    <div className="mx-4 mb-3 flex flex-col gap-2">
      {/* 验证码引导：与进度面板并列，与凭证采集互斥 */}
      {manualOtp && <OtpGuidanceNotice status={status} />}

      {/* 已配置（或收到状态）：显示进度面板；configured=true 面板含重新配置入口 */}
      {(configuredEff || status?.configured) && status && (
        <LoginStatusPanel status={status} onReconfigure={onOpenReconfigure} />
      )}

      {/* 凭证采集：未配置时首次采集；reconfigureOpen 时覆盖编辑 */}
      {(!configuredEff && !manualOtp && !status?.configured) ||
      (reconfigureOpen && (configured || status?.configured)) ? (
        <CredentialSetupPanel
          site={site}
          url={url}
          username=""
          configured={configured || !!status?.configured}
          fieldCandidates={fieldCandidates}
          onSaved={() => {
            onConfiguredChange(true);
            onCloseReconfigure();
          }}
          onDeleted={() => {
            onConfiguredChange(false);
            onCloseReconfigure();
          }}
        />
      ) : null}
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
  loginFlowStatus,
  credentialConfigured,
  credentialSite,
  credentialUrl,
  fieldCandidates,
  onCredentialStatusChange,
  onFiltersApplied,
  onCloseBrowser,
}: BrowserWorkspaceProps) {
  const [reconfigureOpen, setReconfigureOpen] = useState(false);

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

  const isLoginPage = !!loginForm?.is_login_page;
  const unknownCandidates = (fieldCandidates ?? []).filter(
    (f) => f.role === "unknown",
  );

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

      {isLoginPage && credentialSite && (
        <LoginArea
          loginFlowStatus={loginFlowStatus ?? null}
          configured={credentialConfigured ?? false}
          reconfigureOpen={reconfigureOpen}
          site={credentialSite}
          url={credentialUrl ?? loginForm.url}
          fieldCandidates={unknownCandidates}
          onConfiguredChange={(v) => onCredentialStatusChange?.(v)}
          onOpenReconfigure={() => setReconfigureOpen(true)}
          onCloseReconfigure={() => setReconfigureOpen(false)}
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

export default BrowserWorkspace;
