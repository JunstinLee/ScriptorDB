import { Button } from "@heroui/react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import type { SessionMeta } from "../types";
import { getSessionDisplayName } from "../utils/display";

interface SessionListProps {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  showSessionIdHover: boolean;
  onNewSession: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export default function SessionList({
  sessions,
  activeSessionId,
  showSessionIdHover,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
}: SessionListProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between px-4 py-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-graphite">
          Sessions
        </span>
        <Button
          variant="ghost"
          size="sm"
          isIconOnly
          className="text-cobalt hover:bg-cobalt/10"
          onPress={onNewSession}
          aria-label="New session"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {sessions.length > 0 ? (
        <div className="flex flex-col">
          {sessions.map((s) => {
            const displayName = getSessionDisplayName(s.title);
            const isActive = s.session_id === activeSessionId;
            return (
              <div
                key={s.session_id}
                className={`flex cursor-pointer items-center rounded-r-lg px-4 py-2 text-[13px] transition-colors ${
                  isActive
                    ? "border-l-[3px] border-l-cobalt bg-surface text-ink"
                    : "border-l-[3px] border-l-transparent text-graphite hover:bg-surface/50"
                }`}
                role="button"
                tabIndex={0}
                aria-pressed={isActive}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSwitchSession(s.session_id);
                  }
                }}
                onClick={() => onSwitchSession(s.session_id)}
                title={showSessionIdHover ? s.session_id : displayName}
              >
                <span className="flex-1 truncate font-sans">
                  {displayName}
                </span>
                <button
                  className="flex shrink-0 items-center justify-center rounded p-0.5 text-graphite transition-colors hover:text-vermilion focus:outline-2 focus:outline-offset-1 focus:outline-cobalt"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(s.session_id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      e.stopPropagation();
                      onDeleteSession(s.session_id);
                    }
                  }}
                  aria-label={`Delete ${displayName}`}
                  tabIndex={0}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="px-4 py-4 text-[13px] text-graphite">
          No sessions yet. Start a new session to ask about your data.
        </p>
      )}
    </div>
  );
}
