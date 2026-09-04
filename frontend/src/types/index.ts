export interface SessionCreateResponse {
  session_id: string;
}

export interface MessageItem {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  attachments?: string[];
  crawl_url?: string | null;
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
  crawl_url?: string | null;
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
  browser_enabled: boolean;
  providers: ProviderInfo[];
  providers_with_keys: string[];
}

export interface SettingsUpdateRequest {
  llm_provider?: string;
  default_model?: string | null;
  default_model_provider?: string;
  auto_restore_sessions?: boolean;
  browser_enabled?: boolean;
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

export interface LoginFieldInfo {
  role: "username" | "password" | "otp" | "unknown";
  selector: string;
  tag?: string;
  type?: string;
  name?: string;
  id?: string;
  label?: string;
  placeholder?: string;
  autocomplete?: string;
  required?: boolean;
}

export interface LoginFormPayload {
  url: string;
  is_login_page: boolean;
  fields: LoginFieldInfo[];
  submit: LoginFieldInfo | null;
}

export interface HumanTakeoverRequestEvent {
  type: "human_takeover_request";
  run_id: string;
  checkpoint_id?: string;
  reason: string;
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

// ==================== Login Credentials ====================

/** 保存时从当前页捕获的第三项字段特征（供 03 autofill 匹配） */
export interface MatchHints {
  name?: string;
  id?: string;
  label?: string;
  placeholder?: string;
}

/** 附加登录信息（第三项）；无 extra 时传 null，不传空对象 */
export interface ExtraCredential {
  field_label: string;
  value: string;
  match_hints?: MatchHints | null;
}

/** POST /api/credentials 保存请求体 */
export interface LoginCredentialSpec {
  site?: string | null;
  url?: string | null;
  username: string;
  password: string;
  extra?: ExtraCredential | null;
}

/** POST /api/credentials/site-status 请求体 */
export interface SiteStatusRequest {
  url: string;
}

/** 状态响应（非敏感：不含 username/password/extra.value） */
export interface CredentialStatus {
  site: string;
  configured: boolean;
  extra_field_label?: string | null;
  site_label?: string;
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
  | TakeoverCancelledEvent;

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
  /** 错误类别：rate_limit 表示模型限流（HTTP 429），其余为程序错误 */
  error_type?: string | null;
  browser_actions?: BrowserActionEvent[];
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

// ==================== Browser Workspace ====================

/** 浏览器单次操作记录 */
export interface BrowserAction {
  tool: string;
  detail: string;
  timestamp: string;
  success: boolean;
}

/** SSE 推送的实时浏览器操作事件 */
export interface BrowserActionEvent {
  type: "browser_action";
  run_id: string;
  tool: string;
  selector: string;
  coords: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  success: boolean;
  detail: string;
  timestamp: string;
}

/** 浏览器页面历史条目 */
export interface BrowserHistoryEntry {
  url: string;
  title: string;
  timestamp: string;
}

/** 浏览器完整状态快照（对应 GET /api/browser/state 返回值） */
export interface BrowserState {
  launched: boolean;
  url: string | null;
  title: string | null;
  screenshot_available: boolean;
  /** 任务结束后是否已调度自动关闭（倒计时中） */
  idle_close_active: boolean;
  /** 距自动关闭的剩余秒数（未调度时为 0） */
  idle_close_remaining: number;
  actions: BrowserAction[];
  history: BrowserHistoryEntry[];
}

// ==================== Browser Filters ====================

/** browser_apply_filter 支持的筛选动作（与 FILTER_ACTIONS 对齐） */
export type FilterActionType =
  | "select"
  | "input"
  | "toggle"
  | "set_range"
  | "date_range";

/** browser_detect_filters 返回的单个筛选器（Filter Schema 条目） */
export interface FilterSchemaItem {
  name: string;
  type:
    | "select"
    | "combobox"
    | "checkbox"
    | "radio"
    | "tags"
    | "slider"
    | "table_column"
    | "date_range"
    | "date";
  options?: string[];
  current?: string | string[];
  multiple?: boolean;
  min?: string;
  max?: string;
  step?: string;
}

/** browser_detect_filters 返回的 Filter Schema */
export interface FilterSchema {
  url: string;
  count: number;
  filters: FilterSchemaItem[];
}

/** 确认抽屉/面板组装的应用参数（与 browser_apply_filter 参数同名） */
export interface FilterOverrideActions {
  action: FilterActionType;
  target: string;
  value?: string;
  values?: string;
  submit?: boolean;
}

export interface InteractRequest {
  action:
    | "click"
    | "fill"
    | "press_key"
    | "scroll"
    | "navigate"
    | "go_back"
    | "go_forward"
    | FilterActionType;
  selector?: string;
  value?: string;
  scroll_pixels?: number;
  target?: string;
  values?: string;
  submit?: boolean;
}

export interface InteractByCoordsRequest {
  x: number;
  y: number;
  viewport_width: number;
  viewport_height: number;
}

export interface InteractResponse {
  ok: boolean;
  action: string;
  selector: string;
  detail: string;
}

export interface TakeoverCompleteRequest {
  session_id: string;
  result: string;
}

export interface TakeoverEnterControlRequest {
  session_id: string;
}

export interface TakeoverCancelRequest {
  session_id: string;
  run_id?: string;
}

export interface ViewportSizeResponse {
  width: number;
  height: number;
}

// ==================== Browser Cookies & Profiles ====================

export interface CookieInfo {
  name: string;
  domain: string;
  path: string;
  expires: number | null;
  http_only: boolean;
  secure: boolean;
  same_site: string;
}

export interface CookiesResponse {
  cookies: CookieInfo[];
  count: number;
  current_url: string;
}

export interface BrowserProfileItem {
  name: string;
  domain: string;
  cookie_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProfilesResponse {
  profiles: BrowserProfileItem[];
}

export interface SaveProfileRequest {
  name: string;
}

export interface SetCookieRequest {
  name: string;
  value: string;
  domain?: string;
  path?: string;
  secure?: boolean;
  http_only?: boolean;
  same_site?: string;
  expires?: number;
}
