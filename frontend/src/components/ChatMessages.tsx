import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import ChatAvatar from "./common/ChatAvatar";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

export default function ChatMessages({ messages, isLoading }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 pb-32 space-y-4">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex gap-3 ${
            msg.role === "user" ? "justify-end" : "justify-start"
          }`}
        >
          {msg.role === "assistant" && <ChatAvatar role="assistant" />}
          <div
            className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-accent text-accent-foreground"
                : "bg-surface text-surface-foreground border"
            }`}
          >
            <div className="whitespace-pre-wrap break-words">
              {msg.content || (isLoading && i === messages.length - 1 ? (
                <span className="inline-block animate-pulse">...</span>
              ) : null)}
            </div>
          </div>
          {msg.role === "user" && <ChatAvatar role="user" />}
        </div>
      ))}
      {isLoading && messages[messages.length - 1]?.role === "user" && (
        <div className="flex gap-3 justify-start">
          <ChatAvatar role="assistant" />
          <div className="rounded-2xl bg-surface border px-4 py-2.5">
            <span className="inline-block animate-pulse text-sm text-muted">
              Thinking...
            </span>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
