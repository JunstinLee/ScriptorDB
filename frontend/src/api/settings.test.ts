import { describe, expect, it, vi } from "vitest";
import {
  fetchSettings,
  updateSettings,
  saveApiKey,
  deleteApiKey,
  testApiKey,
} from "./settings";

const mockJson = vi.fn(() => Promise.resolve({}));
const mockText = vi.fn(() => Promise.resolve(""));
const mockFetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: mockJson, text: mockText, status: 200 }),
);

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
});

describe("fetchSettings", () => {
  it("fetches /api/settings", async () => {
    mockJson.mockResolvedValueOnce({ llm_provider: "openai", db_url: "sqlite:///test.sqlite" });
    const result = await fetchSettings();
    expect(result).toEqual({ llm_provider: "openai", db_url: "sqlite:///test.sqlite" });
    expect(mockFetch).toHaveBeenCalledWith("/api/settings", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("updateSettings", () => {
  it("sends POST to /api/settings with body", async () => {
    mockJson.mockResolvedValueOnce({ llm_provider: "anthropic" });
    const result = await updateSettings({ llm_provider: "anthropic" });
    expect(result).toEqual({ llm_provider: "anthropic" });
    expect(mockFetch).toHaveBeenCalledWith("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_provider: "anthropic" }),
    });
  });
});

describe("saveApiKey", () => {
  it("sends POST to /api/settings/api-key", async () => {
    mockJson.mockResolvedValueOnce({ ok: true, error: null });
    const result = await saveApiKey({
      provider: "openai",
      api_key: "sk-test",
    });
    expect(result).toEqual({ ok: true, error: null });
    expect(mockFetch).toHaveBeenCalledWith("/api/settings/api-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "openai", api_key: "sk-test" }),
    });
  });
});

describe("deleteApiKey", () => {
  it("sends DELETE to /api/settings/api-key/:provider", async () => {
    mockJson.mockResolvedValueOnce({ ok: true, error: null });
    const result = await deleteApiKey("anthropic");
    expect(result).toEqual({ ok: true, error: null });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/settings/api-key/anthropic",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      },
    );
  });
});

describe("testApiKey", () => {
  it("sends POST to /api/settings/api-key/test", async () => {
    mockJson.mockResolvedValueOnce({ ok: true, error: null });
    const result = await testApiKey({
      provider: "openai",
      api_key: "sk-test",
    });
    expect(result).toEqual({ ok: true, error: null });
    expect(mockFetch).toHaveBeenCalledWith("/api/settings/api-key/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "openai", api_key: "sk-test" }),
    });
  });
});
