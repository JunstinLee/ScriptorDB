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

export interface ProviderInfo {
  name: string;
  base_url: string;
}
