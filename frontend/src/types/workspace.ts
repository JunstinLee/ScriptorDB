import type { ProviderInfo } from "./models";

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
