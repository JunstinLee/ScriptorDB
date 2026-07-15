import type {
  MySQLConfigRequest,
  MySQLConfigResponse,
  WorkspaceActivateRequest,
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceListResponse,
  WorkspaceUpdateRequest,
} from "../types";
import { request, WorkspaceNotSelectedError } from "./core";

export type { WorkspaceItem };

export function fetchWorkspaces(): Promise<WorkspaceListResponse> {
  return request<WorkspaceListResponse>("/workspaces");
}

export async function fetchActiveWorkspace(): Promise<WorkspaceDetail | null> {
  const res = await request<{ workspace: WorkspaceDetail | null }>(
    "/workspaces/active",
  );
  return res.workspace;
}

export function createWorkspace(
  body: WorkspaceCreateRequest,
): Promise<WorkspaceItem> {
  return request<WorkspaceItem>("/workspaces", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return request<WorkspaceDetail>(`/workspaces/${encodeURIComponent(id)}`);
}

export function activateWorkspace(
  id: string,
): Promise<WorkspaceDetail> {
  const body: WorkspaceActivateRequest = { workspace_id: id };
  return request<WorkspaceDetail>(
    `/workspaces/${encodeURIComponent(id)}/activate`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function updateWorkspace(
  id: string,
  body: WorkspaceUpdateRequest,
): Promise<WorkspaceDetail> {
  return request<WorkspaceDetail>(
    `/workspaces/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export function deleteWorkspace(
  id: string,
  deleteFiles = false,
): Promise<{ ok: boolean }> {
  const query = deleteFiles ? "?delete_files=true" : "";
  return request<{ ok: boolean }>(
    `/workspaces/${encodeURIComponent(id)}${query}`,
    { method: "DELETE" },
  );
}

export interface LegacySessionsSummary {
  exists: boolean;
  count: number;
  earliest?: string;
  latest?: string;
}

export function fetchLegacySessionsSummary(): Promise<LegacySessionsSummary> {
  return request<LegacySessionsSummary>("/workspaces/legacy-sessions");
}

export function importLegacySessions(
  workspaceId: string,
): Promise<{ ok: boolean; imported_count: number }> {
  return request<{ ok: boolean; imported_count: number }>(
    `/workspaces/${encodeURIComponent(workspaceId)}/import-legacy-sessions`,
    { method: "POST" },
  );
}

export function configureMySQL(
  workspaceId: string,
  body: MySQLConfigRequest,
): Promise<MySQLConfigResponse> {
  return request<MySQLConfigResponse>(
    `/workspaces/${encodeURIComponent(workspaceId)}/mysql-config`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function resetMySQLConfig(
  workspaceId: string,
): Promise<MySQLConfigResponse> {
  return request<MySQLConfigResponse>(
    `/workspaces/${encodeURIComponent(workspaceId)}/mysql-config`,
    { method: "DELETE" },
  );
}

export { WorkspaceNotSelectedError };
