import { describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSessions } from "./useSessions";

const { mockCreateSession, mockListSessions, mockDeleteSession, mockGetSession } =
  vi.hoisted(() => ({
    mockCreateSession: vi.fn(),
    mockListSessions: vi.fn(),
    mockDeleteSession: vi.fn(),
    mockGetSession: vi.fn(),
  }));

vi.mock("../api/client", () => ({
  createSession: mockCreateSession,
  listSessions: mockListSessions,
  getSession: mockGetSession,
  deleteSession: mockDeleteSession,
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
  mockDeleteSession.mockReset();
  mockGetSession.mockReset();
  localStorage.clear();
});

function makeSessionInfo(
  sessionId: string,
  messages: { role: string; content: string }[],
) {
  return {
    session_id: sessionId,
    messages: messages.map((m) => ({
      ...m,
      timestamp: "2025-01-01T00:00:00Z",
      role: m.role as "user" | "assistant",
    })),
    created_at: "2025-01-01T00:00:00Z",
  };
}

function makeListItem(id: string, title: string | null = null) {
  return {
    session_id: id,
    created_at: "2025-01-01T00:00:00Z",
    last_access: "2025-01-02T00:00:00Z",
    message_count: 2,
    title,
  };
}

describe("useSessions", () => {
  it("loads messages for restored active session", async () => {
    localStorage.setItem("scriptordb:active_session_id", "s1");

    mockListSessions.mockResolvedValueOnce({
      sessions: [makeListItem("s1")],
    });

    mockGetSession.mockResolvedValueOnce(
      makeSessionInfo("s1", [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there!" },
      ]),
    );

    const { result } = renderHook(() => useSessions());

    await waitFor(() => {
      expect(result.current.restored).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "Hello",
    });
  });

  describe("switchSession", () => {
    it("loads messages and persists active session", async () => {
      mockListSessions.mockResolvedValueOnce({
        sessions: [makeListItem("s1")],
      });

      mockGetSession.mockResolvedValueOnce(
        makeSessionInfo("s1", [{ role: "user", content: "Switch test" }]),
      );

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      await act(async () => {
        await result.current.switchSession("s1");
      });

      expect(result.current.activeSessionId).toBe("s1");
      expect(localStorage.getItem("scriptordb:active_session_id")).toBe("s1");

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
      });

      expect(result.current.messages[0].content).toBe("Switch test");
    });

    it("sets empty messages on error", async () => {
      mockListSessions.mockResolvedValueOnce({
        sessions: [makeListItem("s1")],
      });

      mockGetSession.mockRejectedValueOnce(new Error("not found"));

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      await act(async () => {
        await result.current.switchSession("s1");
      });

      expect(result.current.messages).toEqual([]);
    });
  });

  describe("removeSession", () => {
    it("deletes and switches to next session if active", async () => {
      mockListSessions.mockResolvedValueOnce({
        sessions: [makeListItem("s1", "First"), makeListItem("s2", "Second")],
      });

      mockDeleteSession.mockResolvedValueOnce({ ok: true });
      mockGetSession
        .mockResolvedValueOnce(
          makeSessionInfo("s1", [{ role: "user", content: "first session" }]),
        );
      // there are 2 calls for s2: removeSession loads it + useEffect on activeSessionId change
      mockGetSession.mockResolvedValue(
        makeSessionInfo("s2", [{ role: "user", content: "from s2" }]),
      );

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      await act(async () => {
        await result.current.switchSession("s1");
      });

      await waitFor(() => {
        expect(result.current.activeSessionId).toBe("s1");
      });

      await act(async () => {
        await result.current.removeSession("s1");
      });

      expect(mockDeleteSession).toHaveBeenCalledWith("s1");
      expect(result.current.activeSessionId).toBe("s2");
      expect(result.current.sessions).toHaveLength(1);
      expect(localStorage.getItem("scriptordb:active_session_id")).toBe("s2");

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
      });
    });

    it("clears messages when last session is deleted", async () => {
      mockListSessions.mockResolvedValueOnce({
        sessions: [makeListItem("s1")],
      });

      mockDeleteSession.mockResolvedValueOnce({ ok: true });

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      await act(async () => {
        await result.current.switchSession("s1");
      });

      await waitFor(() => {
        expect(result.current.activeSessionId).toBe("s1");
      });

      await act(async () => {
        await result.current.removeSession("s1");
      });

      expect(result.current.activeSessionId).toBeNull();
      expect(result.current.sessions).toHaveLength(0);
      expect(result.current.messages).toEqual([]);
      expect(localStorage.getItem("scriptordb:active_session_id")).toBeNull();
    });

    it("filters from list when deleting non-active session", async () => {
      mockListSessions.mockResolvedValueOnce({
        sessions: [makeListItem("s1"), makeListItem("s2")],
      });

      mockGetSession.mockResolvedValueOnce(
        makeSessionInfo("s1", [{ role: "user", content: "s1 msg" }]),
      );
      mockDeleteSession.mockResolvedValueOnce({ ok: true });

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      await act(async () => {
        await result.current.switchSession("s1");
      });

      await waitFor(() => {
        expect(result.current.activeSessionId).toBe("s1");
      });

      await act(async () => {
        await result.current.removeSession("s2");
      });

      expect(result.current.activeSessionId).toBe("s1");
      expect(result.current.sessions).toHaveLength(1);
    });
  });

  describe("setLoading", () => {
    it("syncs loading state", async () => {
      mockListSessions.mockResolvedValueOnce({ sessions: [] });

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });
      expect(result.current.isLoading).toBe(false);

      act(() => {
        result.current.setLoading(true);
      });
      expect(result.current.isLoading).toBe(true);

      act(() => {
        result.current.setLoading(false);
      });
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe("createNewSession", () => {
    it("creates and returns session id", async () => {
      mockListSessions.mockResolvedValueOnce({ sessions: [] });
      mockCreateSession.mockResolvedValueOnce({
        session_id: "fresh",
      });

      const { result } = renderHook(() => useSessions());

      await waitFor(() => {
        expect(result.current.restored).toBe(true);
      });

      let sid: string | undefined;
      await act(async () => {
        sid = await result.current.createNewSession();
      });

      expect(sid).toBe("fresh");
      expect(result.current.activeSessionId).toBe("fresh");
    });
  });
});
