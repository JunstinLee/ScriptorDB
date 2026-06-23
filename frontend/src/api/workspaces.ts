import type {
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

export { WorkspaceNotSelectedError };
