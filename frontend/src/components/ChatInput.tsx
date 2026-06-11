import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Input, Label, TextField } from "@heroui/react";
import { ArrowUp } from "lucide-react";
import { fetchModels, fetchRecommendedModels } from "../api/client";

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
  const [models, setModels] = useState<string[]>([]);
  const [allModels, setAllModels] = useState<string[]>([]);
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

    fetchRecommendedModels(provider)
      .then((res) => {
        if (fetchedProvider.current !== provider) return;
        if (res.models.length > 0) {
          setModels(res.models);
          setModel(res.models[0]);
          return;
        }
        return fetchModels(provider).then((full) => {
          if (fetchedProvider.current !== provider) return;
          setModels(full.models);
          setAllModels(full.models);
          if (full.models.length > 0) {
            setModel(full.models[0]);
          }
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

  const displayedModels = showAll && allModels.length > 0 ? allModels : models;
  const hasMore = models.length > 0;

  const handleShowMore = useCallback(() => {
    if (allModels.length > 0) {
      setShowAll(true);
      return;
    }
    setLoadingModels(true);
    fetchModels(provider)
      .then((res) => {
        if (fetchedProvider.current !== provider) return;
        setAllModels(res.models);
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
            className="rounded-lg border bg-surface px-2 py-1 text-xs outline-none focus:border-accent"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loadingModels && displayedModels.length === 0}
          >
            <option value="">Default</option>
            {displayedModels.map((m) => (
              <option key={m} value={m}>
                {m}
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
