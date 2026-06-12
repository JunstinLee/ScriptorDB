import type {
  CanonicalModelsResponse,
  ChatRequest,
  DefaultModelResponse,
  HealthResponse,
  ModelsResponse,
  ModelsWithCanonicalResponse,
  SchemaResponse,
  SessionCreateResponse,
  SessionInfo,
} from "../types";

export type { SessionInfo };

const BASE = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function health(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function createSession(): Promise<SessionCreateResponse> {
  return request<SessionCreateResponse>("/sessions", { method: "POST" });
}

export function getSession(sessionId: string): Promise<SessionInfo> {
  return request<SessionInfo>(`/sessions/${sessionId}`);
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function getSchema(): Promise<SchemaResponse> {
  return request<SchemaResponse>("/schema");
}

export function streamChat(
  sessionId: string,
  body: ChatRequest,
  onText: (delta: string) => void,
  onError: (error: string) => void,
  onDone: (fullOutput: string) => void,
): AbortController {
  const controller = new AbortController();

  void (async () => {
    try {
      const res = await fetch(`${BASE}/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        onError(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "message";
      let metadataJson: string | null = null;

      const processLines = (lines: string[]) => {
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (currentEvent === "message") {
              if (data === "[DONE]") continue;
              onText(data);
            } else if (currentEvent === "metadata") {
              metadataJson = data;
            } else if (currentEvent === "error") {
              onError(data);
            }
          } else if (line === "") {
            currentEvent = "message";
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        processLines(lines);
      }

      buffer += decoder.decode();
      processLines(buffer.split("\n"));

      if (metadataJson) {
        try {
          const meta = JSON.parse(metadataJson);
          onDone(meta.full_output ?? "");
        } catch {
          onDone("");
        }
      } else {
        onDone("");
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err.message : "Unknown error");
    }
  })();

  return controller;
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
