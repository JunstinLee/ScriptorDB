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
    resetSessionList,
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
  const lastWorkspaceIdRef = useRef<string | null | undefined>(workspaceId);

  useEffect(() => {
    if (!restored) return;
    if (lastWorkspaceIdRef.current === workspaceId) return;
    lastWorkspaceIdRef.current = workspaceId;
    if (workspaceId === null || workspaceId === undefined) {
      resetSessionList();
      reset();
      return;
    }
    // Workspace switched — clear local state and trigger a refresh so the
    // session list re-fetches from the new workspace.
    resetSessionList();
    reset();
  }, [workspaceId, restored, resetSessionList, reset]);

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
