import { request } from "./core";
import type { UndoListResponse } from "../types/undo";

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
