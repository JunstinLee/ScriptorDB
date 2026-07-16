export interface SessionCreateResponse {
  session_id: string;
}

export interface MessageItem {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface SessionInfo {
  session_id: string;
  messages: MessageItem[];
  runs: Run[];
  created_at: string;
}

export interface ChatRequest {
  prompt: string;
  model?: string | null;
  provider?: string | null;
  attachments?: string[];
}

export interface SchemaColumn {
  name: string;
  type: string;
  pk: boolean;
  notnull: boolean;
  default_value: string | null;
  autoincrement: boolean;
}

export interface SchemaTable {
  name: string;
  sql: string;
  columns: SchemaColumn[];
}

export interface SchemaResponse {
  tables: SchemaTable[];
}

export interface HealthResponse {
  status: string;
  provider: string;
  model: string;
}

export interface ModelsResponse {
  models: string[];
}

export interface DefaultModelResponse {
  model: string | null;
}

export interface CanonicalModelItem {
  slug: string;
  family: string;
  display_name: string;
  description: string;
  tags: string[];
  provider_specific_id?: string | null;
  available_providers?: string[] | null;
}

export interface CanonicalModelsResponse {
  models: CanonicalModelItem[];
}

export interface ModelEntry {
  provider_specific_id: string;
  canonical_slug: string | null;
  display_name: string | null;
  family: string | null;
}

export interface ModelsWithCanonicalResponse {
  models: ModelEntry[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  attachments?: string[];
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

export interface ProviderInfo {
  name: string;
  base_url: string;
}

export interface WorkspaceItem {
  id: string;
  name: string;
  path: string;
  created_at: string;
}

export interface WorkspaceDetail extends WorkspaceItem {
  db_url: string;
  llm_provider: string;
  llm_model: string | null;
  mysql_host?: string;
  mysql_port?: number;
  mysql_user?: string;
  mysql_db?: string;
  mysql_password_set?: boolean;
}

export interface MySQLConfigRequest {
  host: string;
  port: number;
  user: string;
  db: string;
  password: string;
  test_first?: boolean;
}

export interface MySQLConfigResponse {
  ok: boolean;
  db_url: string;
  host: string;
  port: number;
  user: string;
  db: string;
  mysql_password_set: boolean;
  message?: string | null;
  error_code?: string | null;
  error_type?: string | null;
}

export interface ActiveWorkspaceResponse {
  workspace: WorkspaceDetail | null;
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceItem[];
}

export interface WorkspaceCreateRequest {
  name: string;
  path?: string | null;
  db_url?: string | null;
}

export interface WorkspaceActivateRequest {
  workspace_id: string;
}

export interface WorkspaceUpdateRequest {
  name?: string;
}

export interface SettingsResponse {
  workspace_id: string | null;
  llm_provider: string;
  db_url: string;
  llm_model: string | null;
  default_models: Record<string, string>;
  auto_restore_sessions: boolean;
  providers: ProviderInfo[];
  providers_with_keys: string[];
}

export interface SettingsUpdateRequest {
  llm_provider?: string;
  default_model?: string | null;
  default_model_provider?: string;
  auto_restore_sessions?: boolean;
}

export interface ApiKeyRequest {
  provider: string;
  api_key: string;
}

export interface ApiKeyTestResponse {
  ok: boolean;
  error: string | null;
}

// --- Agent Run events ---

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
}

export interface ApprovalRequestEvent {
  type: "approval_request";
  run_id: string;
  request_id: string;
  calls: {
    tool_call_id: string;
    tool_name: string;
    args: Record<string, unknown>;
    row_count: number;
    table_name: string;
  }[];
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
  | ApprovalRequestEvent;

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
  status: "running" | "completed" | "error";
  tool_invocations: ToolInvocation[];
  trace_steps: TraceStep[];
  final_output: string;
  started_at: string;
  ended_at?: string;
  error_message?: string;
}

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

export interface HistoryMatchSegment {
  text: string;
  highlight: boolean;
}

export interface HistorySearchMatch {
  segments: HistoryMatchSegment[];
}

export interface HistorySearchResultItem {
  session_id: string;
  title: string | null;
  created_at: string;
  last_access: string;
  message_count: number;
  match_count: number;
  matches: HistorySearchMatch[];
}

export interface HistorySearchResponse {
  results: HistorySearchResultItem[];
  total: number;
  offset: number;
  limit: number;
}
