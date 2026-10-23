import { useTranslation } from "react-i18next";
import { Loader2, Search } from "lucide-react";

type RunStatusVariant = "thinking" | "tools" | "crawl";

interface RunStatusProps {
  variant: RunStatusVariant;
  /** 正在执行的工具名，用来说明「在做什么」而不是只说「在忙」 */
  toolName?: string;
}

const DOT_DELAYS = [0, 150, 300];

/**
 * 运行状态的唯一视觉语言：
 * 思考中 = 三点、调用工具 = 旋转、抓取网页 = 脉动图标。
 * RunContainer 与 ChatMessages 共用，避免同一状态出现两种标记。
 */
export default function RunStatus({ variant, toolName }: RunStatusProps) {
  const { t } = useTranslation();

  const label =
    variant === "crawl"
      ? t("chat.fetching_web_page")
      : variant === "tools"
        ? t("chat.calling_tools")
        : t("chat.assistant_working");

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-w-0 items-center gap-2 text-sm text-graphite"
    >
      {variant === "crawl" && (
        <Search className="h-4 w-4 shrink-0 text-cobalt animate-pulse" aria-hidden />
      )}
      {variant === "tools" && (
        <Loader2 className="h-4 w-4 shrink-0 text-cobalt animate-spin" aria-hidden />
      )}
      {variant === "thinking" && (
        <span className="flex shrink-0 gap-0.5" aria-hidden>
          {DOT_DELAYS.map((delay) => (
            <span
              key={delay}
              className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
      )}
      <span className="shrink-0">{label}</span>
      {toolName && (
        <code className="truncate font-mono text-xs text-muted">{toolName}</code>
      )}
    </div>
  );
}
