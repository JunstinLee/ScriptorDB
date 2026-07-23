import { useEffect, useRef } from "react";
import { Search, Sparkles, Undo2, User, Wrench } from "lucide-react";
import type { ChatMessage, Run, UndoGroup } from "../types";
import RunContainer from "./RunContainer";
import MarkdownRenderer from "./common/MarkdownRenderer";

interface ChatMessagesProps {
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  undoGroups: UndoGroup[];
  onRevertToHere: (groupId: number) => void;
  onHighlightRun: (runId: string) => void;
}

export default function ChatMessages({
  messages,
  runs,
  isLoading,
  undoGroups,
  onRevertToHere,
  onHighlightRun,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, runs]);

  if (messages.length === 0 && runs.length === 0) return null;

  let runIndex = 0;

  const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
  const crawlNotCompleted = !runs.some((run) =>
    run.tool_invocations.some(
      (t) => t.tool_name === "crawl_webpage" && (t.status === "success" || t.status === "error"),
    ),
  );
  const isCrawling = lastUserMsg?.crawl_url != null && crawlNotCompleted;

  return (
    <div className="px-4 py-4 space-y-4">
      {messages.map((msg, i) => {
        if (msg.role === "user") {
          return (
            <div key={`msg-${i}`} className="flex flex-col gap-1.5 message-enter">
              <div className="flex items-center gap-1.5 text-graphite">
                <User className="h-3 w-3" />
                <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
                  You
                </span>
              </div>
              <div className="border-l-[3px] border-l-amber bg-amber/8 px-3 py-2 space-y-2">
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {msg.attachments.map((path) => (
                      <span
                        key={path}
                        className="inline-flex items-center gap-1 rounded-md border border-grid bg-surface px-2 py-1 text-xs text-ink"
                        title={path}
                      >
                        {path.split("/").pop()}
                      </span>
                    ))}
                  </div>
                )}
                {msg.crawl_url && (
                  <div className="flex flex-wrap gap-2">
                    <span
                      className="inline-flex items-center gap-1 rounded-md border border-grid bg-surface px-2 py-1 text-xs text-ink"
                      title={msg.crawl_url}
                    >
                      <Search className="h-3 w-3 text-cobalt" />
                      {msg.crawl_url}
                    </span>
                  </div>
                )}
                <div className="text-[14px] text-ink whitespace-pre-wrap break-words leading-relaxed">
                  {msg.content}
                </div>
              </div>
            </div>
          );
        }

        const run = runs[runIndex++];
        if (run) {
          const undoGroup = undoGroups.find(
            (g) => g.run_id === run.run_id && g.status === "completed",
          );
          return (
            <div key={`run-${run.run_id}`} className="flex flex-col gap-1.5 message-enter">
              <div className="flex items-center gap-1.5 text-graphite">
                <Sparkles className="h-3 w-3" />
                <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
                  Assistant
                </span>
              </div>
              <div className="rounded-lg border border-grid bg-surface overflow-hidden">
                <RunContainer run={run} />
              </div>
              <div className="flex justify-end gap-1">
                <button
                  type="button"
                  onClick={() => onHighlightRun(run.run_id)}
                  disabled={run.tool_invocations.length === 0}
                  title={
                    run.tool_invocations.length === 0
                      ? "No tools to highlight"
                      : "Highlight in tool panel"
                  }
                  className="rounded-md p-1 text-graphite hover:text-cobalt hover:bg-cobalt/8 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-graphite disabled:hover:bg-transparent"
                >
                  <Wrench className="h-3.5 w-3.5" />
                </button>
                {undoGroup ? (
                  <button
                    type="button"
                    onClick={() => onRevertToHere(undoGroup.id)}
                    title="Undo"
                    className="rounded-md px-1.5 py-1 text-graphite hover:text-cobalt hover:bg-cobalt/8 transition-colors flex items-center gap-1"
                  >
                    <Undo2 className="h-3.5 w-3.5" />
                    <span className="text-[11px]">Undo</span>
                  </button>
                ) : null}
              </div>
            </div>
          );
        }

        return (
          <div key={`msg-${i}`} className="flex flex-col gap-1.5 message-enter">
            <div className="flex items-center gap-1.5 text-graphite">
              <Sparkles className="h-3 w-3" />
              <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
                Assistant
              </span>
            </div>
            <div className="rounded-lg border border-grid bg-surface px-4 py-3">
              <MarkdownRenderer content={msg.content} />
            </div>
          </div>
        );
      })}

      {isLoading &&
        runs.length > runIndex &&
        runs.slice(runIndex).map((run) => (
          <div key={`pending-${run.run_id}`} className="flex flex-col gap-1.5 message-enter">
            <div className="flex items-center gap-1.5 text-graphite">
              <Sparkles className="h-3 w-3" />
              <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
                Assistant
              </span>
            </div>
            <div className="rounded-lg border border-grid bg-surface overflow-hidden">
              <RunContainer run={run} />
            </div>
          </div>
        ))}

      {isLoading && isCrawling && !runs.some(r => r.status === "running") && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5 text-graphite">
            <Sparkles className="h-3 w-3" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
              Assistant
            </span>
          </div>
          <div className="rounded-lg border border-grid bg-surface px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-graphite">
              <Search className="h-4 w-4 text-cobalt animate-pulse" />
              <span>Fetching web page…</span>
            </div>
          </div>
        </div>
      )}

      {isLoading && !isCrawling && !runs.some(r => r.status === "running") && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5 text-graphite">
            <Sparkles className="h-3 w-3" />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
              Assistant
            </span>
          </div>
          <div className="rounded-lg border border-grid bg-surface px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-graphite">
              <span>Assistant is working</span>
              <span className="flex gap-0.5">
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-cobalt animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
