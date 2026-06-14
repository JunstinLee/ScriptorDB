import type {
  CanonicalModelsResponse,
  DefaultModelResponse,
  HealthResponse,
  ModelsResponse,
  ModelsWithCanonicalResponse,
} from "../types";
import { request } from "./core";

export function health(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function fetchModels(provider: string): Promise<ModelsResponse> {
  return request<ModelsResponse>(`/models?provider=${encodeURIComponent(provider)}`);
}

export function fetchRecommendedModels(provider: string): Promise<ModelsResponse> {
  return request<ModelsResponse>(`/models/recommended?provider=${encodeURIComponent(provider)}`);
}

export function fetchDefaultModel(provider: string): Promise<DefaultModelResponse> {
  return request<DefaultModelResponse>(`/models/default?provider=${encodeURIComponent(provider)}`);
}

export function fetchCanonicalModels(
  provider: string = "",
): Promise<CanonicalModelsResponse> {
  const q = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return request<CanonicalModelsResponse>(`/canonical-models${q}`);
}

export function fetchModelsWithCanonical(
  provider: string,
): Promise<ModelsWithCanonicalResponse> {
  return request<ModelsWithCanonicalResponse>(
    `/models/with-canonical?provider=${encodeURIComponent(provider)}`,
  );
}
