import { useCallback } from "react";
import { Label } from "@heroui/react";
import { PROVIDERS } from "../constants";
import { useModelSelector } from "../hooks/useModelSelector";
import { getSessionDisplayName } from "../utils/display";

interface ChatHeaderProps {
  activeSessionId: string | null;
  activeSessionTitle: string | null;
  showSessionIdHover: boolean;
  settingsChanged: number;
  onSelectionChange: (model: string, provider: string) => void;
}

export default function ChatHeader({
  activeSessionId,
  activeSessionTitle,
  showSessionIdHover,
  settingsChanged,
  onSelectionChange,
}: ChatHeaderProps) {
  const {
    provider,
    setProvider,
    model,
    setModel,
    models,
    loadingModels,
    formatModelLabel,
  } = useModelSelector(settingsChanged, onSelectionChange);

  const handleProviderChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setProvider(e.target.value);
    },
    [setProvider],
  );

  const handleModelChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newModel = e.target.value;
      setModel(newModel);
      onSelectionChange(newModel, provider);
    },
    [provider, setModel, onSelectionChange],
  );

  if (!activeSessionId) return null;

  return (
    <div className="flex items-center justify-between border-b px-4 py-2.5">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Session:</span>
          <span
            className="text-xs font-medium"
            title={showSessionIdHover ? activeSessionId : undefined}
          >
            {getSessionDisplayName(activeSessionTitle)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted" htmlFor="header-provider">
            Provider:
          </Label>
          <select
            id="header-provider"
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent"
            value={provider}
            onChange={handleProviderChange}
          >
            <option value="">Default</option>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted" htmlFor="header-model">
            Model:
          </Label>
          <select
            id="header-model"
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent max-w-[24rem]"
            value={model}
            onChange={handleModelChange}
            disabled={loadingModels && models.length === 0}
          >
            <option value="">Default</option>
            {models.map((entry) => (
              <option key={entry.provider_specific_id} value={entry.provider_specific_id}>
                {formatModelLabel(entry)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
