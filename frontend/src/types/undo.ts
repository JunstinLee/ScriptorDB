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
