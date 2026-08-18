import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useModelSelector } from "./useModelSelector";
import {
  fetchSettings,
  fetchRecommendedModels,
  fetchModelsWithCanonical,
} from "../api/client";
import type { SettingsResponse } from "../types";

vi.mock("../api/client", () => ({
  fetchSettings: vi.fn(),
  fetchRecommendedModels: vi.fn(),
  fetchModelsWithCanonical: vi.fn(),
}));

const emptySettings: SettingsResponse = {
  workspace_id: null,
  llm_provider: "",
  db_url: "",
  llm_model: null,
  default_models: {},
  auto_restore_sessions: false,
  browser_enabled: false,
  providers: [],
  providers_with_keys: [],
};

function settings(overrides: Partial<SettingsResponse>): SettingsResponse {
  return { ...emptySettings, ...overrides };
}

function makeEntry(id: string) {
  return {
    provider_specific_id: id,
    canonical_slug: null,
    display_name: null,
    family: null,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchSettings).mockResolvedValue(emptySettings);
  vi.mocked(fetchRecommendedModels).mockResolvedValue({ models: [] });
  vi.mocked(fetchModelsWithCanonical).mockResolvedValue({ models: [] });
});

describe("useModelSelector", () => {
  it("sets provider and saved model from fetchSettings on mount", async () => {
    vi.mocked(fetchSettings).mockResolvedValueOnce(
      settings({ llm_provider: "openai", llm_model: "gpt-4" }),
    );

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("openai");
    });
  });

  it("clears state when fetchSettings fails", async () => {
    vi.mocked(fetchSettings).mockRejectedValueOnce(new Error("down"));

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("");
    });

    expect(result.current.model).toBe("");
    expect(result.current.models).toEqual([]);
  });

  it("fetches models when provider is set", async () => {
    vi.mocked(fetchSettings).mockResolvedValueOnce(
      settings({ llm_provider: "openai", llm_model: null }),
    );
    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["gpt-4o", "gpt-4o-mini"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("gpt-4o"), makeEntry("gpt-4o-mini")],
    });

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(fetchRecommendedModels).toHaveBeenCalledWith("openai");
    });
    await waitFor(() => {
      expect(result.current.models).toHaveLength(2);
    });

    expect(result.current.models[0].provider_specific_id).toBe("gpt-4o");
    expect(onSelectionChange).toHaveBeenCalledWith("gpt-4o", "openai");
  });

  it("selects saved model from settings when it exists in list", async () => {
    vi.mocked(fetchSettings).mockResolvedValueOnce(
      settings({ llm_provider: "openai", llm_model: "gpt-4o-mini" }),
    );
    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["gpt-4o", "gpt-4o-mini"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("gpt-4o"), makeEntry("gpt-4o-mini")],
    });

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.model).toBe("gpt-4o-mini");
    });

    expect(onSelectionChange).toHaveBeenCalledWith("gpt-4o-mini", "openai");
  });

  it("falls back to first model when saved model is not in list", async () => {
    vi.mocked(fetchSettings).mockResolvedValueOnce(
      settings({ llm_provider: "groq", llm_model: "nonexistent" }),
    );
    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["llama-3", "mixtral"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("llama-3"), makeEntry("mixtral")],
    });

    const { result } = renderHook(() =>
      useModelSelector(0, vi.fn()),
    );

    await waitFor(() => {
      expect(result.current.model).toBe("llama-3");
    });
  });

  it("re-fetches when settingsChanged increments", async () => {
    vi.mocked(fetchSettings)
      .mockResolvedValueOnce(
        settings({ llm_provider: "openai", llm_model: null }),
      )
      .mockResolvedValueOnce(
        settings({ llm_provider: "anthropic", llm_model: null }),
      );

    const { result, rerender } = renderHook(
      ({ sc }) => useModelSelector(sc, vi.fn()),
      { initialProps: { sc: 0 } },
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("openai");
    });

    rerender({ sc: 1 });

    await waitFor(() => {
      expect(result.current.provider).toBe("anthropic");
    });

    expect(fetchSettings).toHaveBeenCalledTimes(2);
  });

  describe("formatModelLabel", () => {
    it("returns provider_specific_id when display_name is null", async () => {
      const { result } = renderHook(() =>
        useModelSelector(0, vi.fn()),
      );

      await waitFor(() => {
        expect(fetchSettings).toHaveBeenCalled();
      });

      const label = result.current.formatModelLabel({
        provider_specific_id: "gpt-4o",
        canonical_slug: null,
        display_name: null,
        family: null,
      });
      expect(label).toBe("gpt-4o");
    });

    it("returns display name when present", async () => {
      const { result } = renderHook(() =>
        useModelSelector(0, vi.fn()),
      );

      await waitFor(() => {
        expect(fetchSettings).toHaveBeenCalled();
      });

      const label = result.current.formatModelLabel({
        provider_specific_id: "gpt-4o-2024",
        canonical_slug: "gpt-4o",
        display_name: "GPT-4o",
        family: "gpt",
      });
      expect(label).toBe("GPT-4o");
    });
  });
});
