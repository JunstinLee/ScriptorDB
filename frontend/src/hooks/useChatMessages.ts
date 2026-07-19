import { useCallback, useState } from "react";
import type { ChatMessage } from "../types";

export function useChatMessages() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addUserMessage = useCallback((content: string, attachments?: string[], crawlUrl?: string | null) => {
    const msg: ChatMessage = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
      attachments,
      crawl_url: crawlUrl,
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
            { ...last, content: fullOutput || last.content },
          ];
        }
        return [
          ...prev,
          {
            role: "assistant" as const,
            content: fullOutput,
            timestamp: new Date().toISOString(),
          },
        ];
      });
    },
    [],
  );

  const reset = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    setMessages,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    reset,
  };
}
