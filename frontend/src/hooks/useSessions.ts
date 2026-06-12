import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, SessionListItem } from "../types";
import {
  createSession,
  deleteSession,
  getSession,
  listSessions,
} from "../api/client";
import type { SessionInfo } from "../api/client";

interface SessionMeta {
  session_id: string;
  created_at: string;
  title: string;
}

const TITLE_MAX_LEN = 24;
const DEFAULT_TITLE = "New Chat";
const ACTIVE_SESSION_KEY = "scriptordb:active_session_id";

function deriveTitle(info: SessionInfo): string {
  const firstUser = info.messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return DEFAULT_TITLE;
  const cleaned = firstUser.content.replace(/\s+/g, " ").trim();
  return cleaned.length > TITLE_MAX_LEN ? `${cleaned.slice(0, TITLE_MAX_LEN)}…` : cleaned;
}

function metaFromListItem(item: SessionListItem, fallbackTitle: string): SessionMeta {
  return {
    session_id: item.session_id,
    created_at: item.created_at,
    title: item.title || fallbackTitle,
  };
}

async function loadSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const info: SessionInfo = await getSession(sessionId);
  return info.messages.map((m) => ({
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
  }));
}

async function loadSessionTitle(sessionId: string): Promise<string> {
  const info: SessionInfo = await getSession(sessionId);
  return deriveTitle(info);
}

function readStoredActiveSession(): string | null {
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY);
  } catch {
    return null;
  }
}

function writeStoredActiveSession(id: string | null): void {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_SESSION_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  } catch {
    // ignore quota / privacy mode errors
  }
}

export function useSessions() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [restored, setRestored] = useState(false);
  const initialised = useRef(false);

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

  const restoreInitialState = useCallback(async () => {
    if (initialised.current) return;
    initialised.current = true;
    setIsLoading(true);
    try {
      const items = await refreshSessionList();
      const metaList = buildMetaList(items);
      setSessions(metaList);

      const stored = readStoredActiveSession();
      const stillExists = stored && metaList.find((s) => s.session_id === stored);
      if (stillExists) {
        setActiveSessionId(stored);
        try {
          setMessages(await loadSessionMessages(stored));
        } catch {
          // session no longer exists on server — clear it
          writeStoredActiveSession(null);
          setActiveSessionId(null);
        }
      }
    } catch {
      // server unreachable — leave empty state
    } finally {
      setIsLoading(false);
      setRestored(true);
    }
  }, [buildMetaList, refreshSessionList]);

  useEffect(() => {
    void restoreInitialState();
  }, [restoreInitialState]);

  const createNewSession = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await createSession();
      const meta: SessionMeta = {
        session_id: res.session_id,
        created_at: new Date().toISOString(),
        title: DEFAULT_TITLE,
      };
      setSessions((prev) => [meta, ...prev]);
      setActiveSessionId(meta.session_id);
      setMessages([]);
      writeStoredActiveSession(meta.session_id);
      return meta.session_id;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const removeSession = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(sessionId);
      } catch {
        // server may not know about this session — still remove locally
      }
      let nextActive: string | null = null;
      setSessions((prev) => {
        const remaining = prev.filter((s) => s.session_id !== sessionId);
        if (activeSessionId === sessionId) {
          if (remaining.length > 0) {
            nextActive = remaining[0].session_id;
            void loadSessionMessages(remaining[0].session_id).then(setMessages).catch(() => setMessages([]));
          } else {
            setMessages([]);
          }
        }
        return remaining;
      });
      if (activeSessionId === sessionId) {
        setActiveSessionId(nextActive);
        writeStoredActiveSession(nextActive);
      }
    },
    [activeSessionId],
  );

  const switchSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    writeStoredActiveSession(sessionId);
    setMessages(await loadSessionMessages(sessionId));
  }, []);

  const addUserMessage = useCallback((content: string) => {
    const msg: ChatMessage = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, msg]);
  }, []);

  const appendStreamingText = useCallback((delta: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === "assistant") {
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + delta },
        ];
      }
      return [
        ...prev,
        {
          role: "assistant" as const,
          content: delta,
          timestamp: new Date().toISOString(),
        },
      ];
    });
  }, []);

  const finalizeAssistantMessage = useCallback(
    (fullOutput: string) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant") {
          return [
            ...prev.slice(0, -1),
            { ...last, content: fullOutput },
          ];
        }
        return prev;
      });
    },
    [],
  );

  const setLoading = useCallback((loading: boolean) => {
    setIsLoading(loading);
  }, []);

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
