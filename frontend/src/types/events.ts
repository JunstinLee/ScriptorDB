import type { BrowserActionEvent } from "./browser";
import type { LoginFlowStatusEvent, LoginFormPayload } from "./login";

export interface RunStartEvent {
  type: "run_start";
  run_id: string;
  timestamp: string;
}

export interface RunEndEvent {
  type: "run_end";
  run_id: string;
  timestamp: string;
}

export interface TraceEvent {
  type: "trace";
  run_id: string;
  step: number;
  message: string;
  timestamp: string;
}

export interface ToolCallRunEvent {
  type: "tool_call";
  run_id: string;
  call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  timestamp: string;
}

export interface ToolResultRunEvent {
  type: "tool_result";
  run_id: string;
  call_id: string;
  tool_name: string;
  success: boolean;
  output?: string;
  error_code?: string;
  duration_ms?: number;
  data?: Record<string, unknown>;
  timestamp: string;
}

export interface TextDeltaEvent {
  type: "text_delta";
  run_id: string;
  delta: string;
}

export interface RunMetadataEvent {
  type: "metadata";
  run_id: string;
  full_output: string;
  canonical_slug?: string | null;
  display_name?: string | null;
  provider_specific_id?: string | null;
}

export interface RunErrorEvent {
  type: "error";
  run_id: string;
  message: string;
  error_id?: string | null;
  /** 错误类别：rate_limit 表示模型限流（HTTP 429），其余为程序错误 */
  error_type?: string | null;
  status_code?: number | null;
  model_name?: string | null;
}

export interface ApprovalRequestEvent {
  type: "approval_request";
  run_id: string;
  request_id: string;
  calls: {
    tool_call_id: string;
    tool_name: string;
    args: Record<string, unknown>;
    row_count?: number; // import 专用
    table_name?: string; // import 专用
  }[];
}

export interface HumanTakeoverRequestEvent {
  type: "human_takeover_request";
  run_id: string;
  checkpoint_id?: string;
  reason: string;
  trigger: string;
  current_url: string;
  screenshot_available: boolean;
  timestamp: string;
  login_form?: LoginFormPayload | null;
}

export interface LoginFormDetectedEvent {
  type: "login_form_detected";
  run_id: string;
  login_form: LoginFormPayload;
  timestamp: string;
}

export interface TakeoverStateChangeEvent {
  type: "takeover_state_change";
  run_id: string;
  state: "waiting_human" | "human_control" | "resuming" | "cancelled";
  reason: string;
  trigger: string;
  timestamp: string;
}

export interface TakeoverCancelledEvent {
  type: "takeover_cancelled";
  run_id: string;
  reason: string;
  timestamp: string;
}

/** 总线历史被截断：订阅者拿到的是残缺历史，前端仅记 warn 后继续消费 */
export interface StreamTruncatedEvent {
  type: "stream_truncated";
  run_id: string;
  /** 该序号之前的事件已被丢弃 */
  dropped_before: number;
}

export type StreamRunEvent =
  | RunStartEvent
  | RunEndEvent
  | TraceEvent
  | ToolCallRunEvent
  | ToolResultRunEvent
  | TextDeltaEvent
  | RunMetadataEvent
  | RunErrorEvent
  | ApprovalRequestEvent
  | BrowserActionEvent
  | LoginFormDetectedEvent
  | HumanTakeoverRequestEvent
  | TakeoverStateChangeEvent
  | TakeoverCancelledEvent
  | StreamTruncatedEvent
  | LoginFlowStatusEvent;
