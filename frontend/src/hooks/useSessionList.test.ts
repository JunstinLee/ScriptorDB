import { describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSessionList } from "./useSessionList";

const { mockCreateSession, mockListSessions } = vi.hoisted(() => ({
  mockCreateSession: vi.fn(),
  mockListSessions: vi.fn(),
}));

vi.mock("../api/client", () => ({
  createSession: mockCreateSession,
  listSessions: mockListSessions,
  getSession: vi.fn(),
  deleteSession: vi.fn(),
  getSchema: vi.fn(),
  health: vi.fn(),
  fetchModels: vi.fn(),
  fetchRecommendedModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchCanonicalModels: vi.fn(),
  fetchModelsWithCanonical: vi.fn(),
  fetchSettings: vi.fn(),
  updateSettings: vi.fn(),
  saveApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
  testApiKey: vi.fn(),
  streamChat: vi.fn(),
}));

beforeEach(() => {
  mockCreateSession.mockReset();
  mockListSessions.mockReset();
});

function makeItem(
  id: string,
  title: string | null = null,
) {
  return {
    session_id: id,
    created_at: "2025-01-01T00:00:00Z",
    last_access: "2025-01-02T00:00:00Z",
    message_count: 3,
    title,
  };
}

describe("useSessionList", () => {
  it("loads session list on mount", async () => {
    mockListSessions.mockResolvedValueOnce({
      sessions: [makeItem("s1", "Chat 1"), makeItem("s2", "Chat 2")],
    });

    const { result } = renderHook(() => useSessionList());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.sessions).toHaveLength(2);
    expect(result.current.sessions[0].session_id).toBe("s1");
    expect(result.current.sessions[0].title).toBe("Chat 1");
    expect(result.current.restored).toBe(true);
  });

  it("restores stored active session", async () => {
    localStorage.setItem("scriptordb:active_session_id", "s2");

    mockListSessions.mockResolvedValueOnce({
      sessions: [makeItem("s1", "Chat 1"), makeItem("s2", "Chat 2")],
    });

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    expect(result.current.activeSessionId).toBe("s2");
  });

  it("ignores stored session id if not in list", async () => {
    localStorage.setItem("scriptordb:active_session_id", "nonexistent");

    mockListSessions.mockResolvedValueOnce({
      sessions: [makeItem("s1")],
    });

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    expect(result.current.activeSessionId).toBeNull();
  });

  it("creates a new session", async () => {
    mockListSessions.mockResolvedValueOnce({ sessions: [] });
    mockCreateSession.mockResolvedValueOnce({
      session_id: "new-session",
    });

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    let sessionId: string | undefined;
    await act(async () => {
      sessionId = await result.current.createNewSession();
    });

    expect(sessionId).toBe("new-session");
    expect(result.current.activeSessionId).toBe("new-session");
    expect(result.current.sessions).toHaveLength(1);
    expect(result.current.sessions[0].session_id).toBe("new-session");
    expect(localStorage.getItem("scriptordb:active_session_id")).toBe(
      "new-session",
    );
  });

  it("handles listSessions error gracefully", async () => {
    mockListSessions.mockRejectedValueOnce(new Error("unreachable"));

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    expect(result.current.sessions).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("updateSessionTitle changes title in list", async () => {
    mockListSessions.mockResolvedValueOnce({
      sessions: [makeItem("s1", "Old Title")],
    });

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    act(() => {
      result.current.updateSessionTitle("s1", "New Title");
    });

    expect(result.current.sessions[0].title).toBe("New Title");
  });

  it("refreshSessions reloads from server", async () => {
    mockListSessions
      .mockResolvedValueOnce({ sessions: [makeItem("s1")] })
      .mockResolvedValueOnce({
        sessions: [makeItem("s1"), makeItem("s2")],
      });

    const { result } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    expect(result.current.sessions).toHaveLength(1);

    await act(async () => {
      await result.current.refreshSessions();
    });

    expect(result.current.sessions).toHaveLength(2);
  });

  it("only initialises once on mount", async () => {
    mockListSessions.mockResolvedValue({ sessions: [] });

    const { rerender } = renderHook(() => useSessionList());

    await waitFor(() => {
      expect(mockListSessions).toHaveBeenCalledTimes(1);
    });

    rerender();

    await waitFor(() => {
      expect(mockListSessions).toHaveBeenCalledTimes(1);
    });
  });
});
