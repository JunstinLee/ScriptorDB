import { useEffect, useState } from "react";
import { health } from "../api/client";
import { getSessionDisplayName } from "../utils/display";

interface ChatHeaderProps {
  activeSessionId: string | null;
  activeSessionTitle: string | null;
  showSessionIdHover: boolean;
  settingsChanged: number;
}

export default function ChatHeader({
  activeSessionId,
  activeSessionTitle,
  showSessionIdHover,
  settingsChanged,
}: ChatHeaderProps) {
  const [provider, setProvider] = useState<string>("");
  const [model, setModel] = useState<string>("");

  useEffect(() => {
    health().then((h) => {
      setProvider(h.provider);
      setModel(h.model.split(":").pop() ?? h.model);
    }).catch(() => {
      setProvider("");
      setModel("");
    });
  }, [activeSessionId, settingsChanged]);

  if (!activeSessionId) return null;

  return (
    <div className="flex items-center justify-between border-b px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted">
          Session:
        </span>
        <span
          className="text-xs font-medium"
          title={showSessionIdHover ? activeSessionId : undefined}
        >
          {getSessionDisplayName(activeSessionTitle)}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted">
        <span>
          Provider: <span className="font-medium text-foreground">{provider || "..."}</span>
        </span>
        <span>
          Model: <span className="font-medium text-foreground">{model || "..."}</span>
        </span>
      </div>
    </div>
  );
}
