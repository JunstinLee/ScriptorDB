import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Input, Label, TextField } from "@heroui/react";
import { ArrowUp } from "lucide-react";
import {
  fetchDefaultModel,
  fetchModelsWithCanonical,
  fetchRecommendedModels,
  health,
} from "../api/client";
import type { ModelEntry } from "../types";

interface ChatInputProps {
  onSend: (prompt: string, model?: string | null, provider?: string | null) => void;
  disabled: boolean;
  settingsChanged: number;
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

export default function ChatInput({ onSend, disabled, settingsChanged }: ChatInputProps) {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState<string>("");
  const [provider, setProvider] = useState<string>("");
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState<string>("");
  const fetchedProvider = useRef<string>("");

  useEffect(() => {
    health().then((h) => {
      setProvider(h.provider);
      const m = h.model.split(":").pop() ?? h.model;
      setModel(m);
    }).catch(() => {});
  }, [settingsChanged]);

  useEffect(() => {
    if (!provider) {
      setModels([]);
      setModel("");
      setModelsError("");
      fetchedProvider.current = "";
      return;
    }

    setModel("");
    setModelsError("");
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
          setModelsError("No recommended models for this provider.");
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
            if (def.model && entries.some((e) => e.provider_specific_id === def.model)) {
              setModel(def.model);
            } else {
              setModel(entries[0].provider_specific_id);
            }
          });
        });
      })
      .catch((err) => {
        if (fetchedProvider.current !== provider) return;
        setModels([]);
        setModelsError(err instanceof Error ? err.message : "Failed to load models.");
      })
      .finally(() => {
        if (fetchedProvider.current === provider) {
          setLoadingModels(false);
        }
      });
  }, [provider]);

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
            name="prompt"
          >
            <Label>Message</Label>
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
          <Label className="text-xs text-muted" htmlFor="chat-model">
            Model:
          </Label>
          <select
            id="chat-model"
            name="model"
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent max-w-[28rem]"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loadingModels && models.length === 0}
          >
            <option value="">Default</option>
            {models.map((entry) => (
              <option key={entry.provider_specific_id} value={entry.provider_specific_id}>
                {formatModelLabel(entry)}
              </option>
            ))}
          </select>
          {modelsError && (
            <span className="text-xs text-warning whitespace-nowrap">
              {modelsError}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted" htmlFor="chat-provider">
            Provider:
          </Label>
          <select
            id="chat-provider"
            name="provider"
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
