import { CheckCircle2, Circle, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import type { LoginFlowStatus } from "../types";

/**
 * 登录流程状态面板（03）：展示自动填写的非敏感进度（用户名/密码/附加信息
 * 是否已填、是否填好、错误），configured=true 的已配置态提供「重新配置」
 * 入口（点击展开 01 的 CredentialSetupPanel）。
 *
 * 非敏感：只消费 LoginFlowStatus 布尔与错误文案，绝不含凭证明文/验证码值。
 */
export function LoginStatusPanel({
  status,
  onReconfigure,
}: {
  status: LoginFlowStatus | null;
  onReconfigure?: () => void;
}) {
  if (!status || !status.login_form_detected) {
    return null;
  }

  const steps: { label: string; done: boolean }[] = [];
  if (status.username_filled) steps.push({ label: "Account filled", done: true });
  if (status.password_filled) steps.push({ label: "Password filled", done: true });
  if (status.extra_required) {
    steps.push({
      label: status.extra_filled ? "Extra info filled" : "Extra info pending",
      done: status.extra_filled,
    });
  }
  if (status.manual_otp_guided) {
    steps.push({ label: "Verification code — manual in Chrome", done: false });
  }

  return (
    <div className="rounded-xl border border-grid bg-surface px-4 py-3">
      <div className="flex items-center gap-2">
        {status.fill_ok && !status.manual_otp_guided ? (
          <ShieldCheck className="size-4 shrink-0 text-emerald-500" />
        ) : (
          <ShieldCheck className="size-4 shrink-0 text-accent" />
        )}
        <p className="text-sm font-semibold text-foreground">
          {status.configured ? "Auto-fill" : "Login info not configured"}
        </p>
        {status.configured && (
          <button
            onClick={onReconfigure}
            className="ml-auto inline-flex items-center gap-1 rounded-lg border border-grid px-2 py-1 text-[11px] text-muted hover:bg-surface/70 hover:text-foreground"
            title="Reconfigure saved login info"
          >
            <RefreshCw className="size-3" />
            Reconfigure
          </button>
        )}
      </div>

      {steps.length > 0 && (
        <ul className="mt-2 space-y-1">
          {steps.map((s, i) => (
            <li
              key={i}
              className="flex items-center gap-1.5 text-xs text-muted"
            >
              {s.done ? (
                <CheckCircle2 className="size-3.5 text-emerald-500" />
              ) : (
                <Circle className="size-3.5 text-graphite" />
              )}
              {s.label}
            </li>
          ))}
        </ul>
      )}

      {status.fill_error && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-danger">
          <XCircle className="mt-0.5 size-3.5 shrink-0" />
          {status.fill_error}
        </p>
      )}
    </div>
  );
}

export default LoginStatusPanel;
