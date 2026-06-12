import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Input, Label, TextField } from "@heroui/react";
import { ArrowUp } from "lucide-react";
import {
  fetchDefaultModel,
  fetchModels,
  fetchModelsWithCanonical,
  fetchRecommendedModels,
} from "../api/client";
import type { ModelEntry } from "../types";

interface ChatInputProps {
  onSend: (prompt: string, model?: string | null, provider?: string | null) => void;
  disabled: boolean;
}

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

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState<string>("");
  const [provider, setProvider] = useState<string>("");
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [allModels, setAllModels] = useState<ModelEntry[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const fetchedProvider = useRef<string>("");

  useEffect(() => {
    if (!provider) {
      setModels([]);
      setAllModels([]);
      setShowAll(false);
      setModel("");
      fetchedProvider.current = "";
      return;
    }

    setModel("");
    setShowAll(false);
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
        if (res.models.length > 0) {
          return fetchModelsWithCanonical(provider).then((withCanon) => {
            if (fetchedProvider.current !== provider) return;
            const map = new Map(
              withCanon.models.map((m) => [m.provider_specific_id, m]),
            );
            const entries: ModelEntry[] = res.models.map((id) => map.get(id) ?? canonicalize([id])[0]);
            setModels(entries);
            return fetchDefaultModel(provider).then((def) => {
              if (fetchedProvider.current !== provider) return;
              if (def.model && entries.some((e) => e.provider_specific_id === def.model)) {
                setModel(def.model);
              } else if (entries.length > 0) {
                setModel(entries[0].provider_specific_id);
              }
            });
          });
        }
        return fetchModels(provider).then((full) => {
          if (fetchedProvider.current !== provider) return;
          return fetchModelsWithCanonical(provider).then((withCanon) => {
            if (fetchedProvider.current !== provider) return;
            const map = new Map(
              withCanon.models.map((m) => [m.provider_specific_id, m]),
            );
            const fullEntries: ModelEntry[] = full.models.map(
              (id) => map.get(id) ?? canonicalize([id])[0],
            );
            setModels(fullEntries);
            setAllModels(fullEntries);
            return fetchDefaultModel(provider).then((def) => {
              if (fetchedProvider.current !== provider) return;
              if (def.model && fullEntries.some((e) => e.provider_specific_id === def.model)) {
                setModel(def.model);
              } else if (fullEntries.length > 0) {
                setModel(fullEntries[0].provider_specific_id);
              }
            });
          });
        });
      })
      .catch(() => {
        if (fetchedProvider.current !== provider) return;
        setModels([]);
      })
      .finally(() => {
        if (fetchedProvider.current === provider) {
          setLoadingModels(false);
        }
      });
  }, [provider]);

  const displayedModels = useMemo(
    () => (showAll && allModels.length > 0 ? allModels : models),
    [showAll, allModels, models],
  );
  const hasMore = models.length > 0;

  const handleShowMore = useCallback(() => {
    if (allModels.length > 0) {
      setShowAll(true);
      return;
    }
    setLoadingModels(true);
    fetchModelsWithCanonical(provider)
      .then((withCanon) => {
        if (fetchedProvider.current !== provider) return;
        setAllModels(withCanon.models);
        setShowAll(true);
      })
      .finally(() => {
        if (fetchedProvider.current === provider) {
          setLoadingModels(false);
        }
      });
  }, [provider, allModels]);

  const handleSend = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    onSend(trimmed, model || null, provider || null);
    setPrompt("");
  }, [prompt, model, provider, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const formatModelLabel = (entry: ModelEntry): string => {
    if (entry.display_name && entry.display_name !== entry.provider_specific_id) {
      return `${entry.display_name}  ·  ${entry.provider_specific_id}`;
    }
    return entry.provider_specific_id;
  };

  return (
    <div className="border-t px-4 py-3">
      <div className="flex gap-2">
        <div className="flex-1">
          <TextField
            value={prompt}
            onChange={setPrompt}
            className="w-full"
          >
            <Input
              placeholder="Ask about your database..."
              disabled={disabled}
              onKeyDown={handleKeyDown}
            />
          </TextField>
        </div>
        <Button
          variant="primary"
          isIconOnly
          onPress={handleSend}
          isDisabled={disabled || !prompt.trim()}
          aria-label="Send"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted">Model:</Label>
          <select
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent max-w-[28rem]"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loadingModels && displayedModels.length === 0}
          >
            <option value="">Default</option>
            {displayedModels.map((entry) => (
              <option key={entry.provider_specific_id} value={entry.provider_specific_id}>
                {formatModelLabel(entry)}
              </option>
            ))}
          </select>
          {hasMore && !showAll && (
            <button
              type="button"
              className="text-xs text-accent hover:underline whitespace-nowrap"
              onClick={handleShowMore}
            >
              More...
            </button>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted">Provider:</Label>
          <select
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="">Default</option>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
