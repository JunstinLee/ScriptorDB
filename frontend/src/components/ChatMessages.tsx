import { useEffect, useRef } from "react";
import { Wrench } from "lucide-react";
import type { ChatMessage, Run } from "../types";
import ChatAvatar from "./common/ChatAvatar";
import RunContainer from "./RunContainer";
import MarkdownRenderer from "./common/MarkdownRenderer";

interface ChatMessagesProps {
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  onHighlightRun: (runId: string) => void;
}

export default function ChatMessages({
  messages,
  runs,
  isLoading,
  onHighlightRun,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, runs]);

  if (messages.length === 0 && runs.length === 0) return null;

  let runIndex = 0;

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

        const run = runs[runIndex++];
        if (run) {
          return (
            <div key={`run-${run.run_id}`} className="flex gap-3 justify-start">
              <ChatAvatar role="assistant" />
              <div className="flex-1 min-w-0">
                <RunContainer run={run} />
              </div>
              <button
                type="button"
                onClick={() => onHighlightRun(run.run_id)}
                disabled={run.tool_invocations.length === 0}
                title={run.tool_invocations.length === 0 ? "无工具调用" : "查看工具调用"}
                className="shrink-0 self-start mt-1 rounded-lg p-1.5 text-muted hover:text-foreground hover:bg-default-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Wrench className="h-4 w-4" />
              </button>
            </div>
          );
        }

        return (
          <div key={`msg-${i}`} className="flex gap-3 justify-start">
            <ChatAvatar role="assistant" />
            <div className="max-w-[75%] rounded-2xl px-4 py-2.5 bg-surface text-surface-foreground border">
              <MarkdownRenderer content={msg.content} />
            </div>
          </div>
        );
      })}

      {isLoading &&
        runs.length > runIndex &&
        runs.slice(runIndex).map((run) => (
          <div
            key={`pending-${run.run_id}`}
            className="flex gap-3 justify-start"
          >
            <ChatAvatar role="assistant" />
            <div className="max-w-[85%] min-w-0">
              <RunContainer run={run} />
            </div>
          </div>
        ))}

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
