import type { BrowserActionEvent } from "./browser";

export interface ToolInvocation {
  call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  status: "running" | "success" | "error";
  output?: string;
  error_code?: string;
  duration_ms?: number;
  data?: Record<string, unknown>;
  started_at: string;
  ended_at?: string;
}

export interface TraceStep {
  step: number;
  message: string;
  timestamp: string;
}

export interface Run {
  run_id: string;
  status: "running" | "completed" | "error" | "cancelled";
  tool_invocations: ToolInvocation[];
  trace_steps: TraceStep[];
  final_output: string;
  started_at: string;
  ended_at?: string;
  error_message?: string;
  /** 错误类别：rate_limit 表示模型限流（HTTP 429），其余为程序错误 */
  error_type?: string | null;
  browser_actions?: BrowserActionEvent[];
}
