import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useApiKeyStatus } from "./useApiKeyStatus";
import { fetchApiKeyStatus } from "../api/client";
import type { ApiKeyStatus } from "../types";

vi.mock("../api/client", () => ({
  fetchApiKeyStatus: vi.fn(),
}));

function status(overrides: Partial<ApiKeyStatus>): ApiKeyStatus {
  return {
    provider: "deepseek",
    status: "valid",
    error: null,
    checked_at: "2026-01-01T00:00:00+00:00",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchApiKeyStatus).mockResolvedValue(status({}));
});

describe("useApiKeyStatus", () => {
  it("does not probe when there is no workspace", async () => {
    const { result } = renderHook(() => useApiKeyStatus(null));

    expect(fetchApiKeyStatus).not.toHaveBeenCalled();
    expect(result.current.kind).toBeNull();
    expect(result.current.provider).toBeNull();
  });

  it("reports the checked status on mount", async () => {
    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "missing" }),
    );

    const { result } = renderHook(() => useApiKeyStatus("ws-1"));

    await waitFor(() => {
      expect(result.current.kind).toBe("missing");
    });
    expect(result.current.provider).toBe("deepseek");
    expect(fetchApiKeyStatus).toHaveBeenCalledWith(undefined, false);
  });

  it("keeps the previous status when a check fails", async () => {
    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "valid" }),
    );

    const { result } = renderHook(() => useApiKeyStatus("ws-1"));
    await waitFor(() => {
      expect(result.current.kind).toBe("valid");
    });

    vi.mocked(fetchApiKeyStatus).mockRejectedValueOnce(new Error("down"));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.kind).toBe("valid");
  });

  it("re-checks when the workspace changes", async () => {
    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "missing" }),
    );

    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useApiKeyStatus(id),
      { initialProps: { id: "ws-1" as string | null } },
    );
    await waitFor(() => {
      expect(result.current.kind).toBe("missing");
    });

    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "valid" }),
    );
    rerender({ id: "ws-2" });

    await waitFor(() => {
      expect(result.current.kind).toBe("valid");
    });
    expect(fetchApiKeyStatus).toHaveBeenCalledTimes(2);
  });

  it("force-refreshes when refresh() is called", async () => {
    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "invalid", error: "API key rejected (HTTP 401)" }),
    );

    const { result } = renderHook(() => useApiKeyStatus("ws-1"));
    await waitFor(() => {
      expect(result.current.kind).toBe("invalid");
    });
    expect(result.current.error).toBe("API key rejected (HTTP 401)");

    vi.mocked(fetchApiKeyStatus).mockResolvedValueOnce(
      status({ status: "valid" }),
    );
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.kind).toBe("valid");
    expect(fetchApiKeyStatus).toHaveBeenLastCalledWith(undefined, true);
  });
});
