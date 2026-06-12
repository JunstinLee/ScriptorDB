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
  created_at: string;
}

export interface ChatRequest {
  prompt: string;
  model?: string | null;
  provider?: string | null;
}

export interface SchemaTable {
  name: string;
  sql: string;
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

export interface SSEEvent {
  type: "text" | "metadata" | "error" | "done";
  data: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
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

export interface SettingsResponse {
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
