import { useEffect, useRef } from "react";
import type { ChatMessage, Run } from "../types";
import ChatAvatar from "./common/ChatAvatar";
import RunContainer from "./RunContainer";

interface ChatMessagesProps {
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
}

export default function ChatMessages({
  messages,
  runs,
  isLoading,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, runs]);

  if (messages.length === 0 && runs.length === 0) return null;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 pb-32 space-y-4">
      {messages.map((msg, i) => {
        if (msg.role === "user") {
          return (
            <div key={`msg-${i}`} className="flex gap-3 justify-end">
              <div className="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-accent text-accent-foreground">
                <div className="whitespace-pre-wrap break-words">
                  {msg.content}
                </div>
              </div>
              <ChatAvatar role="user" />
            </div>
          );
        }

        const run = runs[i];
        if (run) {
          return (
            <div key={`run-${run.run_id}`} className="flex gap-3 justify-start">
              <ChatAvatar role="assistant" />
              <div className="max-w-[85%] min-w-0">
                <RunContainer run={run} />
              </div>
            </div>
          );
        }

        return (
          <div key={`msg-${i}`} className="flex gap-3 justify-start">
            <ChatAvatar role="assistant" />
            <div className="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-surface text-surface-foreground border">
              <div className="whitespace-pre-wrap break-words">
                {msg.content}
              </div>
            </div>
          </div>
        );
      })}

      {isLoading && runs.length > 0 && runs[runs.length - 1]?.status === "running" && (
        <div className="flex gap-3 justify-start">
          <ChatAvatar role="assistant" />
          <div className="max-w-[85%] min-w-0">
            <RunContainer run={runs[runs.length - 1]} />
          </div>
        </div>
      )}

      {isLoading && runs.length === 0 && (
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
