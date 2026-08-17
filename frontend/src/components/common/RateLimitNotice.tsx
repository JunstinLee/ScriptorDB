import { Clock3 } from "lucide-react";

interface RateLimitNoticeProps {
  message?: string;
  modelName?: string | null;
}

/**
 * 模型限流（HTTP 429）提示。与程序错误区分展示：
 * 限流是临时状态，提示用户稍后重试，而非暴露为系统故障。
 */
export default function RateLimitNotice({
  message,
  modelName,
}: RateLimitNoticeProps) {
  return (
    <div className="border-l-[3px] border-l-amber bg-amber/10 px-4 py-3">
      <div className="flex items-start gap-2">
        <Clock3 className="h-4 w-4 text-amber shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-amber">Rate limited (HTTP 429)</p>
          <p className="text-sm text-amber/80">
            {message ??
              "Too many requests. Please try again shortly."}
          </p>
          {modelName && (
            <p className="text-xs text-graphite/70">
              Model: {modelName}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
