import { useCallback, useEffect, useRef } from "react";
import { useSessionList } from "./useSessionList";
import { useChatMessages } from "./useChatMessages";
import { deleteSession } from "../api/client";
import {
  loadSessionMessages,
  loadSessionTitle,
  writeStoredActiveSession,
} from "../utils/sessions";

export function useSessions() {
  const {
    sessions,
    activeSessionId,
    isLoading,
    restored,
    setSessions,
    setActiveSessionId,
    setIsLoading,
    createNewSession,
    refreshSessions,
    updateSessionTitle,
  } = useSessionList();

  const {
    messages,
    setMessages,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    reset,
  } = useChatMessages();

  const requestedSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!restored) return;
    const targetId = activeSessionId;
    requestedSessionIdRef.current = targetId;
    if (targetId === null) {
      setMessages([]);
      return;
    }
    setMessages([]);
    loadSessionMessages(targetId)
      .then((msgs) => {
        if (requestedSessionIdRef.current !== targetId) return;
        setMessages(msgs);
      })
      .catch(() => {
        if (requestedSessionIdRef.current !== targetId) return;
        setMessages([]);
      });
  }, [restored, activeSessionId, setMessages]);

  const switchSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      writeStoredActiveSession(sessionId);
    },
    [setActiveSessionId],
  );

  const removeSession = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(sessionId);
      } catch {
        // server may not know — still remove locally
      }

      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        setSessions(remaining);
        const nextActive =
          remaining.length > 0 ? remaining[0].session_id : null;
        setActiveSessionId(nextActive);
        writeStoredActiveSession(nextActive);
        if (!nextActive) {
          requestedSessionIdRef.current = null;
          reset();
        }
      } else {
        setSessions((prev) =>
          prev.filter((s) => s.session_id !== sessionId),
        );
      }
    },
    [
      activeSessionId,
      sessions,
      setSessions,
      setActiveSessionId,
      reset,
    ],
  );

  const setLoading = useCallback(
    (loading: boolean) => {
      setIsLoading(loading);
    },
    [setIsLoading],
  );

  const refreshSessionTitle = useCallback(
    async (sessionId: string) => {
      try {
        const title = await loadSessionTitle(sessionId);
        updateSessionTitle(sessionId, title);
      } catch {
        // keep previous title on failure
      }
    },
    [updateSessionTitle],
  );

  return {
    sessions,
    activeSessionId,
    messages,
    isLoading,
    restored,
    createNewSession,
    removeSession,
    switchSession,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    setLoading,
    refreshSessionTitle,
    refreshSessions,
  };
}
