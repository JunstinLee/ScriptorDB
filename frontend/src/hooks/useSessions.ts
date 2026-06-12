import { useCallback, useState } from "react";
import type { ChatMessage } from "../types";
import {
  createSession,
  deleteSession,
  getSession,
} from "../api/client";
import type { SessionInfo } from "../api/client";

interface SessionMeta {
  session_id: string;
  created_at: string;
  title: string;
}

const TITLE_MAX_LEN = 24;
const DEFAULT_TITLE = "New Chat";

function deriveTitle(info: SessionInfo): string {
  const firstUser = info.messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return DEFAULT_TITLE;
  const cleaned = firstUser.content.replace(/\s+/g, " ").trim();
  return cleaned.length > TITLE_MAX_LEN ? `${cleaned.slice(0, TITLE_MAX_LEN)}…` : cleaned;
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

export function useSessions() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const updateSessionTitle = useCallback(
    (sessionId: string, title: string) => {
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? { ...s, title } : s)),
      );
    },
    [],
  );

  const createNewSession = useCallback(async () => {
    setIsLoading(true);
    const res = await createSession();
    const meta: SessionMeta = {
      session_id: res.session_id,
      created_at: new Date().toISOString(),
      title: DEFAULT_TITLE,
    };
    setSessions((prev) => [meta, ...prev]);
    setActiveSessionId(meta.session_id);
    setMessages([]);
    setIsLoading(false);
    return meta.session_id;
  }, []);

  const removeSession = useCallback(
    async (sessionId: string) => {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        if (remaining.length > 0) {
          const first = remaining[0];
          setActiveSessionId(first.session_id);
          setMessages(await loadSessionMessages(first.session_id));
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    },
    [activeSessionId, sessions],
  );

  const switchSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
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

  return {
    sessions,
    activeSessionId,
    messages,
    isLoading,
    createNewSession,
    removeSession,
    switchSession,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    setLoading,
    refreshSessionTitle,
  };
}
