import type {
  ApiKeyRequest,
  ApiKeyTestResponse,
  SettingsResponse,
  SettingsUpdateRequest,
} from "../types";
import { request } from "./core";

export function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings");
}

export function updateSettings(
  body: SettingsUpdateRequest,
): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function saveApiKey(body: ApiKeyRequest): Promise<ApiKeyTestResponse> {
  return request<ApiKeyTestResponse>("/settings/api-key", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteApiKey(provider: string): Promise<ApiKeyTestResponse> {
  return request<ApiKeyTestResponse>(
    `/settings/api-key/${encodeURIComponent(provider)}`,
    { method: "DELETE" },
  );
}

export function testApiKey(
  body: ApiKeyRequest,
): Promise<ApiKeyTestResponse> {
  return request<ApiKeyTestResponse>("/settings/api-key/test", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
