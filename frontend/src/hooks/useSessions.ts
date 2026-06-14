import { useCallback, useEffect } from "react";
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
  } = useChatMessages();

  useEffect(() => {
    if (restored && activeSessionId) {
      loadSessionMessages(activeSessionId)
        .then(setMessages)
        .catch(() => {});
    }
  }, [restored, activeSessionId, setMessages]);

  const switchSession = useCallback(
    async (sessionId: string) => {
      setActiveSessionId(sessionId);
      writeStoredActiveSession(sessionId);
      try {
        setMessages(await loadSessionMessages(sessionId));
      } catch {
        setMessages([]);
      }
    },
    [setActiveSessionId, setMessages],
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
        if (nextActive) {
          loadSessionMessages(nextActive)
            .then(setMessages)
            .catch(() => setMessages([]));
        } else {
          setMessages([]);
        }
      } else {
        setSessions((prev) =>
          prev.filter((s) => s.session_id !== sessionId),
        );
      }
    },
    [activeSessionId, sessions, setSessions, setActiveSessionId, setMessages],
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
