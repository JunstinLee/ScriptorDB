import { useCallback, useState } from "react";
import { Button, Input, TextField } from "@heroui/react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSend: (prompt: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [prompt, setPrompt] = useState("");

  const handleSend = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setPrompt("");
  }, [prompt, onSend]);

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
            name="prompt"
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
    </div>
  );
}
