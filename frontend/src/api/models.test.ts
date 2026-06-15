import { describe, expect, it, vi } from "vitest";
import {
  health,
  fetchModels,
  fetchRecommendedModels,
  fetchDefaultModel,
  fetchCanonicalModels,
  fetchModelsWithCanonical,
} from "./models";

const mockJson = vi.fn(() => Promise.resolve({}));
const mockText = vi.fn(() => Promise.resolve(""));
const mockFetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: mockJson, text: mockText, status: 200 }),
);

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
});

describe("health", () => {
  it("fetches /api/health", async () => {
    mockJson.mockResolvedValueOnce({
      status: "ok",
      provider: "openai",
      model: "gpt-4",
    });
    const result = await health();
    expect(result).toEqual({ status: "ok", provider: "openai", model: "gpt-4" });
    expect(mockFetch).toHaveBeenCalledWith("/api/health", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("fetchModels", () => {
  it("encodes provider param", async () => {
    mockJson.mockResolvedValueOnce({ models: ["a", "b"] });
    const result = await fetchModels("openai");
    expect(result).toEqual({ models: ["a", "b"] });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models?provider=openai",
      expect.anything(),
    );
  });
});

describe("fetchRecommendedModels", () => {
  it("fetches recommended models", async () => {
    mockJson.mockResolvedValueOnce({ models: ["best-model"] });
    const result = await fetchRecommendedModels("anthropic");
    expect(result).toEqual({ models: ["best-model"] });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models/recommended?provider=anthropic",
      expect.anything(),
    );
  });
});

describe("fetchDefaultModel", () => {
  it("fetches default model for provider", async () => {
    mockJson.mockResolvedValueOnce({ model: "gpt-4o" });
    const result = await fetchDefaultModel("openai");
    expect(result).toEqual({ model: "gpt-4o" });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models/default?provider=openai",
      expect.anything(),
    );
  });
});

describe("fetchCanonicalModels", () => {
  it("fetches without provider param when empty", async () => {
    mockJson.mockResolvedValueOnce({ models: [] });
    await fetchCanonicalModels();
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/canonical-models",
      expect.anything(),
    );
  });

  it("fetches with provider param", async () => {
    mockJson.mockResolvedValueOnce({ models: [] });
    await fetchCanonicalModels("openai");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/canonical-models?provider=openai",
      expect.anything(),
    );
  });
});

describe("fetchModelsWithCanonical", () => {
  it("fetches models with canonical mapping", async () => {
    mockJson.mockResolvedValueOnce({ models: [] });
    await fetchModelsWithCanonical("groq");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models/with-canonical?provider=groq",
      expect.anything(),
    );
  });
});
