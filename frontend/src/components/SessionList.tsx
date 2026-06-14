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
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between px-2 py-1">
        <span className="text-xs font-semibold uppercase text-muted tracking-wide">
          Sessions
        </span>
        <Button
          variant="ghost"
          size="sm"
          isIconOnly
          onPress={onNewSession}
          aria-label="New session"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex flex-col gap-0.5">
        {sessions.map((s) => {
          const displayName = getSessionDisplayName(s.title);
          const isActive = s.session_id === activeSessionId;
          return (
            <div
              key={s.session_id}
              className={`group flex cursor-pointer items-center rounded-lg px-2 py-1.5 text-sm transition-colors ${
                isActive
                  ? "bg-accent/15 text-accent"
                  : "hover:bg-default/50 text-foreground"
              }`}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onSwitchSession(s.session_id);
                }
              }}
              tabIndex={0}
              role="button"
              aria-pressed={isActive}
            >
              <span
                className="flex-1 truncate"
                onClick={() => onSwitchSession(s.session_id)}
                title={showSessionIdHover ? s.session_id : displayName}
              >
                {displayName}
              </span>
              <Button
                variant="ghost"
                size="sm"
                isIconOnly
                className="opacity-0 group-hover:opacity-100 h-6 w-6"
                onPress={() => onDeleteSession(s.session_id)}
                aria-label={`Delete ${displayName}`}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          );
        })}
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-muted text-center">
            No sessions yet. Start a new one!
          </p>
        )}
      </div>
    </div>
  );
}
