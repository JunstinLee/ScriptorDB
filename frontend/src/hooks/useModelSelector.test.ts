import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../api/models", () => ({
  health: vi.fn(),
  fetchModels: vi.fn(),
  fetchRecommendedModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchCanonicalModels: vi.fn(),
  fetchModelsWithCanonical: vi.fn(),
}));

import {
  health,
  fetchRecommendedModels,
  fetchModelsWithCanonical,
  fetchDefaultModel,
} from "../api/client";
import { renderHook, waitFor } from "@testing-library/react";
import { useModelSelector } from "./useModelSelector";

beforeEach(() => {
  vi.clearAllMocks();
});

function makeEntry(id: string) {
  return {
    provider_specific_id: id,
    canonical_slug: null,
    display_name: null,
    family: null,
  };
}

describe("useModelSelector", () => {
  it("fetches provider from health on mount", async () => {
    vi.mocked(health).mockResolvedValueOnce({
      status: "ok",
      provider: "openai",
      model: "gpt-4",
    });

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("openai");
    });
  });

  it("handles health fetch failure", async () => {
    vi.mocked(health).mockRejectedValueOnce(new Error("down"));

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("");
    });

    expect(result.current.model).toBe("");
  });

  it("fetches models when provider is set", async () => {
    vi.mocked(health).mockResolvedValueOnce({
      status: "ok",
      provider: "openai",
      model: "gpt-4",
    });

    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["gpt-4o", "gpt-4o-mini"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("gpt-4o"), makeEntry("gpt-4o-mini")],
    });
    vi.mocked(fetchDefaultModel).mockResolvedValueOnce({ model: "gpt-4o" });

    const onSelectionChange = vi.fn();
    renderHook(() => useModelSelector(0, onSelectionChange));

    await waitFor(() => {
      expect(fetchRecommendedModels).toHaveBeenCalledWith("openai");
    });
    await waitFor(() => {
      expect(fetchModelsWithCanonical).toHaveBeenCalledWith("openai");
    });
    await waitFor(() => {
      expect(fetchDefaultModel).toHaveBeenCalledWith("openai");
    });
  });

  it("selects default model when it exists in list", async () => {
    vi.mocked(health).mockResolvedValueOnce({
      status: "ok",
      provider: "openai",
      model: "gpt-4",
    });
    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["gpt-4o", "gpt-4o-mini"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("gpt-4o"), makeEntry("gpt-4o-mini")],
    });
    vi.mocked(fetchDefaultModel).mockResolvedValueOnce({
      model: "gpt-4o-mini",
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

  it("falls back to first model when default is not in list", async () => {
    vi.mocked(health).mockResolvedValueOnce({
      status: "ok",
      provider: "groq",
      model: "llama",
    });
    vi.mocked(fetchRecommendedModels).mockResolvedValueOnce({
      models: ["llama-3", "mixtral"],
    });
    vi.mocked(fetchModelsWithCanonical).mockResolvedValueOnce({
      models: [makeEntry("llama-3"), makeEntry("mixtral")],
    });
    vi.mocked(fetchDefaultModel).mockResolvedValueOnce({
      model: "nonexistent",
    });

    const onSelectionChange = vi.fn();
    const { result } = renderHook(() =>
      useModelSelector(0, onSelectionChange),
    );

    await waitFor(() => {
      expect(result.current.model).toBe("llama-3");
    });
  });

  it("re-fetches when settingsChanged increments", async () => {
    vi.mocked(health)
      .mockResolvedValueOnce({
        status: "ok",
        provider: "openai",
        model: "gpt-4",
      })
      .mockResolvedValueOnce({
        status: "ok",
        provider: "anthropic",
        model: "claude",
      });

    const onSelectionChange = vi.fn();
    const { result, rerender } = renderHook(
      ({ sc }) => useModelSelector(sc, onSelectionChange),
      { initialProps: { sc: 0 } },
    );

    await waitFor(() => {
      expect(result.current.provider).toBe("openai");
    });

    rerender({ sc: 1 });

    await waitFor(() => {
      expect(result.current.provider).toBe("anthropic");
    });

    expect(health).toHaveBeenCalledTimes(2);
  });

  describe("formatModelLabel", () => {
    it("returns provider_specific_id when display_name is null", () => {
      vi.mocked(health).mockResolvedValueOnce({
        status: "ok",
        provider: "test",
        model: "",
      });

      const { result } = renderHook(() =>
        useModelSelector(0, vi.fn()),
      );

      const label = result.current.formatModelLabel({
        provider_specific_id: "gpt-4o",
        canonical_slug: null,
        display_name: null,
        family: null,
      });
      expect(label).toBe("gpt-4o");
    });

    it("returns display name with provider id when different", () => {
      vi.mocked(health).mockResolvedValueOnce({
        status: "ok",
        provider: "test",
        model: "",
      });

      const { result } = renderHook(() =>
        useModelSelector(0, vi.fn()),
      );

      const label = result.current.formatModelLabel({
        provider_specific_id: "gpt-4o-2024",
        canonical_slug: "gpt-4o",
        display_name: "GPT-4o",
        family: "gpt",
      });
      expect(label).toBe("GPT-4o  ·  gpt-4o-2024");
    });
  });
});
