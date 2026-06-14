import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchDefaultModel,
  fetchModelsWithCanonical,
  fetchRecommendedModels,
  health,
} from "../api/client";
import type { ModelEntry } from "../types";
import { getSessionDisplayName } from "../utils/display";
import { Label } from "@heroui/react";

const PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "groq",
  "mistral",
  "openrouter",
  "nim",
  "together",
];

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
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const fetchedProvider = useRef("");
  const onSelectionChangeRef = useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;

  useEffect(() => {
    health()
      .then((h) => {
        setProvider(h.provider);
      })
      .catch(() => {
        setProvider("");
        setModel("");
        setModels([]);
      });
  }, [settingsChanged]);

  useEffect(() => {
    if (!provider) {
      setModels([]);
      setModel("");
      fetchedProvider.current = "";
      return;
    }

    setModel("");
    setLoadingModels(true);
    fetchedProvider.current = provider;

    const canonicalize = (ids: string[]): ModelEntry[] =>
      ids.map((id) => ({
        provider_specific_id: id,
        canonical_slug: null,
        display_name: null,
        family: null,
      }));

    fetchRecommendedModels(provider)
      .then((res) => {
        if (fetchedProvider.current !== provider) return;
        if (res.models.length === 0) {
          setModels([]);
          onSelectionChangeRef.current("", provider);
          return;
        }
        return fetchModelsWithCanonical(provider).then((withCanon) => {
          if (fetchedProvider.current !== provider) return;
          const map = new Map(
            withCanon.models.map((m) => [m.provider_specific_id, m]),
          );
          const entries: ModelEntry[] = res.models.map(
            (id) => map.get(id) ?? canonicalize([id])[0],
          );
          setModels(entries);
          return fetchDefaultModel(provider).then((def) => {
            if (fetchedProvider.current !== provider) return;
            const selectedModel =
              def.model && entries.some((e) => e.provider_specific_id === def.model)
                ? def.model
                : entries[0]?.provider_specific_id ?? "";
            setModel(selectedModel);
            onSelectionChangeRef.current(selectedModel, provider);
          });
        });
      })
      .catch(() => {
        if (fetchedProvider.current !== provider) return;
        setModels([]);
        setModel("");
        onSelectionChangeRef.current("", provider);
      })
      .finally(() => {
        if (fetchedProvider.current === provider) {
          setLoadingModels(false);
        }
      });
  }, [provider]);

  const handleProviderChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setProvider(e.target.value);
    },
    [],
  );

  const handleModelChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newModel = e.target.value;
      setModel(newModel);
      onSelectionChangeRef.current(newModel, provider);
    },
    [provider],
  );

  const formatModelLabel = (entry: ModelEntry): string => {
    if (entry.display_name && entry.display_name !== entry.provider_specific_id) {
      return `${entry.display_name}  ·  ${entry.provider_specific_id}`;
    }
    return entry.provider_specific_id;
  };

  if (!activeSessionId) return null;

  return (
    <div className="flex items-center justify-between border-b px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted">Session:</span>
        <span
          className="text-xs font-medium"
          title={showSessionIdHover ? activeSessionId : undefined}
        >
          {getSessionDisplayName(activeSessionTitle)}
        </span>
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
