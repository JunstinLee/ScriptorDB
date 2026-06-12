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
