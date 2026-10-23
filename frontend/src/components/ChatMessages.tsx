import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Search, Sparkles, Undo2, User, Wrench } from "lucide-react";
import type { ChatMessage, Run, UndoGroup } from "../types";
import RunContainer from "./RunContainer";
import MarkdownRenderer from "./common/MarkdownRenderer";
import RunStatus from "./common/RunStatus";

interface ChatMessagesProps {
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  undoGroups: UndoGroup[];
  onRevertToHere: (groupId: number) => void;
  onHighlightRun: (runId: string) => void;
}

type Role = "user" | "assistant";

/**
 * 一次渲染里可能出现的块。先摊平成列表再渲染，
 * 角色标签就能按「上一条是不是同一角色」决定是否出现，不用在 JSX 里记状态。
 */
type ChatEntry =
  | { kind: "user"; key: string; role: "user"; message: ChatMessage }
  | { kind: "run"; key: string; role: "assistant"; run: Run }
  | { kind: "text"; key: string; role: "assistant"; message: ChatMessage }
  | { kind: "pending"; key: string; role: "assistant"; run: Run }
  | { kind: "status"; key: string; role: "assistant" };

export default function ChatMessages({
  messages,
  runs,
  isLoading,
  undoGroups,
  onRevertToHere,
  onHighlightRun,
}: ChatMessagesProps) {
  const { t } = useTranslation();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, runs]);

  if (messages.length === 0 && runs.length === 0) return null;

  const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
  const crawlNotCompleted = !runs.some((run) =>
    run.tool_invocations.some(
      (inv) =>
        inv.tool_name === "crawl_webpage" &&
        (inv.status === "success" || inv.status === "error"),
    ),
  );
  const isCrawling = lastUserMsg?.crawl_url != null && crawlNotCompleted;

  const entries: ChatEntry[] = [];
  let runIndex = 0;

  messages.forEach((msg, i) => {
    if (msg.role === "user") {
      entries.push({ kind: "user", key: `msg-${i}`, role: "user", message: msg });
      return;
    }
    const run = runs[runIndex++];
    if (run) {
      entries.push({ kind: "run", key: `run-${run.run_id}`, role: "assistant", run });
    } else {
      entries.push({ kind: "text", key: `msg-${i}`, role: "assistant", message: msg });
    }
  });

  if (isLoading) {
    runs.slice(runIndex).forEach((run) => {
      entries.push({
        kind: "pending",
        key: `pending-${run.run_id}`,
        role: "assistant",
        run,
      });
    });
    if (!runs.some((r) => r.status === "running")) {
      entries.push({ kind: "status", key: "status", role: "assistant" });
    }
  }

  // 角色标签只在角色切换时出现一次，而不是每个块都重复
  const rows = entries.map((entry, idx) => ({
    entry,
    showRoleLabel: idx === 0 || entries[idx - 1].role !== entry.role,
  }));

  const roleLabel = (role: Role) => {
    const Icon = role === "user" ? User : Sparkles;
    return (
      <div className="flex items-center gap-1.5 text-graphite">
        <Icon className="h-3 w-3" />
        <span className="text-[11px] font-medium uppercase tracking-[0.08em]">
          {role === "user" ? t("chat.role.you") : t("chat.role.assistant")}
        </span>
      </div>
    );
  };

  return (
    <div className="px-4 py-4 space-y-4">
      {rows.map(({ entry, showRoleLabel }) => {
        const label = showRoleLabel ? roleLabel(entry.role) : null;

        if (entry.kind === "user") {
          const msg = entry.message;
          return (
            <div key={entry.key} className="flex flex-col gap-1.5 message-enter">
              {label}
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
                <div className="text-[14px] text-ink whitespace-pre-wrap wrap-break-word leading-relaxed">
                  {msg.content}
                </div>
              </div>
            </div>
          );
        }

        if (entry.kind === "run" || entry.kind === "pending") {
          const run = entry.run;
          const undoGroup =
            entry.kind === "run"
              ? undoGroups.find(
                  (g) => g.run_id === run.run_id && g.status === "completed",
                )
              : undefined;
          return (
            <div key={entry.key} className="flex flex-col gap-1.5 message-enter">
              {label}
              <div className="rounded-lg border border-grid bg-surface overflow-hidden">
                <RunContainer run={run} />
              </div>
              {entry.kind === "run" && (
                <div className="flex justify-end gap-1">
                  <button
                    type="button"
                    onClick={() => onHighlightRun(run.run_id)}
                    disabled={run.tool_invocations.length === 0}
                    title={
                      run.tool_invocations.length === 0
                        ? t("chat.no_tools_to_highlight")
                        : t("chat.highlight_in_tool_panel")
                    }
                    className="rounded-md p-1 text-graphite hover:text-cobalt hover:bg-cobalt/8 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-graphite disabled:hover:bg-transparent"
                  >
                    <Wrench className="h-3.5 w-3.5" />
                  </button>
                  {undoGroup ? (
                    <button
                      type="button"
                      onClick={() => onRevertToHere(undoGroup.id)}
                      title={t("chat.undo")}
                      className="rounded-md px-1.5 py-1 text-graphite hover:text-cobalt hover:bg-cobalt/8 transition-colors flex items-center gap-1"
                    >
                      <Undo2 className="h-3.5 w-3.5" />
                      <span className="text-[11px]">{t("chat.undo")}</span>
                    </button>
                  ) : null}
                </div>
              )}
            </div>
          );
        }

        if (entry.kind === "text") {
          return (
            <div key={entry.key} className="flex flex-col gap-1.5 message-enter">
              {label}
              <div className="rounded-lg border border-grid bg-surface px-4 py-3">
                <MarkdownRenderer content={entry.message.content} />
              </div>
            </div>
          );
        }

        return (
          <div key={entry.key} className="flex flex-col gap-1.5">
            {label}
            <div className="rounded-lg border border-grid bg-surface px-4 py-3">
              <RunStatus variant={isCrawling ? "crawl" : "thinking"} />
            </div>
          </div>
        );
      })}

      <div ref={bottomRef} />
    </div>
  );
}
