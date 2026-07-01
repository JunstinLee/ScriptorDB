import { request } from "./core";

export interface UndoGroup {
  id: number;
  session_id: string;
  run_id: string;
  prompt_preview: string;
  started_at: string;
  ended_at: string | null;
  status: "pending" | "completed" | "reverted";
  sequence: number;
}

export interface UndoListResponse {
  groups: UndoGroup[];
}

export function listUndoGroups(): Promise<UndoListResponse> {
  return request<UndoListResponse>("/undo");
}

export function revertUndoGroup(
  groupId: number,
): Promise<{ reverted_group_ids: number[] }> {
  return request<{ reverted_group_ids: number[] }>(`/undo/${groupId}/revert`, {
    method: "POST",
  });
}

export function revertAndTrimSession(
  groupId: number,
): Promise<{ reverted_group_ids: number[]; session_trimmed: boolean }> {
  return request<{ reverted_group_ids: number[]; session_trimmed: boolean }>(
    `/undo/${groupId}/session`,
    { method: "DELETE" },
  );
}
