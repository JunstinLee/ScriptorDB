import { useEffect, useState } from "react";
import { health } from "../api/client";

interface ChatHeaderProps {
  activeSessionId: string | null;
  settingsChanged: number;
}

export default function ChatHeader({ activeSessionId, settingsChanged }: ChatHeaderProps) {
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
        <code className="rounded bg-default/50 px-1.5 py-0.5 text-xs font-mono">
          {activeSessionId.slice(0, 12)}
        </code>
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
