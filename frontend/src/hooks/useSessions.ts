import { useCallback, useEffect, useRef } from "react";
import { useSessionList } from "./useSessionList";
import { useChatMessages } from "./useChatMessages";
import { deleteSession } from "../api/client";
import {
  loadSessionData,
  loadSessionTitle,
  writeStoredActiveSession,
} from "../utils/sessions";
import type { Run } from "../types";

export function useSessions(
  onRunsLoaded?: (sessionId: string, runs: Run[]) => void,
  workspaceId?: string | null,
) {
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
  } = useSessionList(workspaceId);

  const {
    messages,
    setMessages,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    reset,
  } = useChatMessages();

  const requestedSessionIdRef = useRef<string | null>(null);
  const lastWorkspaceIdRef = useRef<string | null | undefined>(workspaceId);

  useEffect(() => {
    if (lastWorkspaceIdRef.current === workspaceId) return;
    lastWorkspaceIdRef.current = workspaceId;
    reset();
  }, [workspaceId, reset]);

  useEffect(() => {
    if (!restored) return;
    const targetId = activeSessionId;
    requestedSessionIdRef.current = targetId;
    if (targetId === null) {
      setMessages([]);
      return;
    }
    setMessages([]);
    loadSessionData(targetId)
      .then(({ messages, runs }) => {
        if (requestedSessionIdRef.current !== targetId) return;
        setMessages(messages);
        onRunsLoaded?.(targetId, runs);
      })
      .catch(() => {
        if (requestedSessionIdRef.current !== targetId) return;
        setMessages([]);
      });
  }, [restored, activeSessionId, setMessages, onRunsLoaded]);

  const switchSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      writeStoredActiveSession(sessionId, workspaceId);
    },
    [setActiveSessionId, workspaceId],
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
        writeStoredActiveSession(nextActive, workspaceId);
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
      workspaceId,
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
