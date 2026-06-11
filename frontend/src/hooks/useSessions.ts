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
}

export function useSessions() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const createNewSession = useCallback(async () => {
    setIsLoading(true);
    const res = await createSession();
    const meta: SessionMeta = {
      session_id: res.session_id,
      created_at: new Date().toISOString(),
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
          const info: SessionInfo = await getSession(first.session_id);
          setMessages(
            info.messages.map((m) => ({
              role: m.role,
              content: m.content,
              timestamp: m.timestamp,
            })),
          );
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
    const info: SessionInfo = await getSession(sessionId);
    setMessages(
      info.messages.map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      })),
    );
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

  const finalizeAssistantMessage = useCallback((fullOutput: string) => {
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
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setIsLoading(loading);
  }, []);

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
  };
}
