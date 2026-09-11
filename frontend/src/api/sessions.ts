import type {
  ActiveRunResponse,
  ApprovalSubmitResponse,
  SchemaResponse,
  SessionCreateResponse,
  SessionInfo,
  SessionListResponse,
} from "../types";
import { request } from "./core";

export type { SessionInfo };

export function createSession(): Promise<SessionCreateResponse> {
  return request<SessionCreateResponse>("/sessions", { method: "POST" });
}

export function listSessions(): Promise<SessionListResponse> {
  return request<SessionListResponse>("/sessions");
}

export function getSession(sessionId: string): Promise<SessionInfo> {
  return request<SessionInfo>(`/sessions/${sessionId}`);
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function getSchema(): Promise<SchemaResponse> {
  return request<SchemaResponse>("/schema");
}

/** 当前活动 run 状态：无活动 run 时 run_id 为空、suspended 为 null。 */
export function fetchActiveRun(sessionId: string): Promise<ActiveRunResponse> {
  return request<ActiveRunResponse>(`/sessions/${sessionId}/active-run`);
}

export function submitApproval(
  sessionId: string,
  requestId: string,
  approvedMap: Record<string, boolean>,
  overrideArgsByCallId?: Record<string, Record<string, unknown>>,
): Promise<ApprovalSubmitResponse> {
  return request<ApprovalSubmitResponse>(`/sessions/${sessionId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: requestId,
      approved_map: approvedMap,
      ...(overrideArgsByCallId
        ? { override_args: overrideArgsByCallId }
        : {}),
    }),
  });
}
