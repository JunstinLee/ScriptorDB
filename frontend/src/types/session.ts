import type { Run } from "./run";

export interface SessionCreateResponse {
  session_id: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  attachments?: string[];
  crawl_url?: string | null;
}

export interface SessionInfo {
  session_id: string;
  messages: ChatMessage[];
  runs: Run[];
  created_at: string;
}

export interface ChatRequest {
  prompt: string;
  model?: string | null;
  provider?: string | null;
  attachments?: string[];
  crawl_url?: string | null;
}

export interface SessionMeta {
  session_id: string;
  created_at: string;
  title: string;
}

export interface SessionListItem {
  session_id: string;
  created_at: string;
  last_access: string;
  message_count: number;
  title: string | null;
}

export interface SessionListResponse {
  sessions: SessionListItem[];
}

/** POST /api/sessions/{id}/approve 响应（成功态；失败态由 HTTPException 承载） */
export interface ApprovalSubmitResponse {
  ok: boolean;
  run_id: string;
}

/** GET /api/sessions/{id}/active-run 响应 */
export interface ActiveRunResponse {
  run_id: string;
  suspended: "takeover" | "approval" | null;
  reason: string;
  last_index: number;
}
