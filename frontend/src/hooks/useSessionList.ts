import { useCallback, useEffect, useRef, useState } from "react";
import type { SessionListItem } from "../types";
import {
  createSession as apiCreateSession,
  listSessions,
} from "../api/client";
import {
  DEFAULT_TITLE,
  metaFromListItem,
  readStoredActiveSession,
  writeStoredActiveSession,
  type SessionMeta,
} from "../utils/sessions";

export function useSessionList(workspaceId?: string | null) {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [restored, setRestored] = useState(false);
  const restoringRef = useRef<string | null | undefined>(null);

  const updateSessionTitle = useCallback(
    (sessionId: string, title: string) => {
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? { ...s, title } : s)),
      );
    },
    [],
  );

  const refreshSessionList = useCallback(async (): Promise<SessionListItem[]> => {
    const resp = await listSessions();
    return resp.sessions;
  }, []);

  const buildMetaList = useCallback(
    (items: SessionListItem[]): SessionMeta[] =>
      items.map((item) => metaFromListItem(item, DEFAULT_TITLE)),
    [],
  );

  const restoreInitialState = useCallback(async (wid: string) => {
    restoringRef.current = wid;
    setIsLoading(true);
    setRestored(false);
    try {
      const items = await refreshSessionList();
      if (restoringRef.current !== wid) return;
      const metaList = buildMetaList(items);
      setSessions(metaList);
      const stored = readStoredActiveSession(wid);
      const stillExists = stored && metaList.find((s) => s.session_id === stored);
      setActiveSessionId(stillExists ? stored : null);
    } catch {
      // server unreachable — leave empty state
    } finally {
      if (restoringRef.current === wid) {
        setIsLoading(false);
        setRestored(true);
      }
    }
  }, [buildMetaList, refreshSessionList]);

  useEffect(() => {
    if (!workspaceId) {
      setSessions([]);
      setActiveSessionId(null);
      setIsLoading(false);
      setRestored(true);
      return;
    }
    void restoreInitialState(workspaceId);
  }, [workspaceId, restoreInitialState]);

  const createNewSession = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiCreateSession();
      const meta: SessionMeta = {
        session_id: res.session_id,
        created_at: new Date().toISOString(),
        title: DEFAULT_TITLE,
      };
      setSessions((prev) => [meta, ...prev]);
      setActiveSessionId(meta.session_id);
      writeStoredActiveSession(meta.session_id, workspaceId);
      return meta.session_id;
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  const refreshSessions = useCallback(async () => {
    try {
      const items = await refreshSessionList();
      setSessions(buildMetaList(items));
    } catch {
      // ignore — keep existing list
    }
  }, [buildMetaList, refreshSessionList]);

  return {
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
    buildMetaList,
    refreshSessionList,
  };
}
