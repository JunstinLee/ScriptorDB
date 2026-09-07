import { MessageCircleQuestion } from "lucide-react";
import type { LoginFlowStatus } from "../types";

/**
 * 验证码手动填写引导（02）：当自动填写已填完长凭证、页面出现验证码
 * （manual_otp_guided=true）时提示用户到真实 Chrome 窗口手动输入。
 *
 * 只读提示：无输入框、无按钮、无持久化调用；完成动作在既有
 * HumanTakeoverDrawer 的 "Finish and resume agent" 上。验证码值
 * 永不进入前端组件 / SSE / 后端。
 */
export function OtpGuidanceNotice({
  status,
}: {
  status: LoginFlowStatus | null;
}) {
  if (!status || !status.manual_otp_guided) {
    return null;
  }
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <MessageCircleQuestion className="mt-0.5 size-4 shrink-0 text-amber-500" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
            Verification code required
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-amber-700/80 dark:text-amber-300/70">
            Account and password were filled in automatically. Enter the
            verification code in the Chrome window, then click{" "}
            <span className="font-medium">Finish and resume agent</span> to
            continue.
          </p>
        </div>
      </div>
    </div>
  );
}

export default OtpGuidanceNotice;
