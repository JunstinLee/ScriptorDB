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

export interface SSEEvent {
  type: "text" | "metadata" | "error" | "done";
  data: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}
