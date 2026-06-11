import { useCallback, useState } from "react";
import { Button, Input, Label, TextField } from "@heroui/react";
import { ArrowUp } from "lucide-react";

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
          >
            <option value="">Default</option>
            <option value="gpt-4o">gpt-4o</option>
            <option value="gpt-4o-mini">gpt-4o-mini</option>
            <option value="claude-sonnet-4">claude-sonnet-4</option>
            <option value="gemini-2.5-flash">gemini-2.5-flash</option>
          </select>
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
