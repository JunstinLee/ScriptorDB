import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input } from "@heroui/react";
import { ArrowUp, X } from "lucide-react";

interface ChatInputProps {
  onSend: (prompt: string, attachments: string[], crawlUrl: string | null) => void;
  disabled: boolean;
  attachments: string[];
  removeAttachment: (path: string) => void;
  uploadError: string | null;
  crawlMode: boolean;
  crawlUrl: string;
  urlError: string | null;
  onCrawlUrlChange: (value: string) => void;
}

export default function ChatInput({ onSend, disabled, attachments, removeAttachment, uploadError, crawlMode, crawlUrl, urlError, onCrawlUrlChange }: ChatInputProps) {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 144)}px`;
  }, []);

  const normalizeUrl = (raw: string): string => {
    if (raw.includes("://")) return raw;
    return `https://${raw}`;
  };

  const handleSend = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed && attachments.length === 0) return;
    if (crawlMode && !crawlUrl.trim()) return;

    onSend(
      trimmed || (crawlMode ? t("chat.crawl_default_prompt") : ""),
      attachments,
      crawlMode ? normalizeUrl(crawlUrl.trim()) : null,
    );
    setPrompt("");
    requestAnimationFrame(() => {
      const ta = textareaRef.current;
      if (ta) {
        ta.style.height = "auto";
      }
    });
  }, [prompt, attachments, crawlMode, crawlUrl, onSend, t]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setPrompt(e.target.value);
      requestAnimationFrame(resizeTextarea);
    },
    [resizeTextarea],
  );

  return (
    <div className="flex flex-col gap-1 px-3 py-2">
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 pb-1">
          {attachments.map((path) => (
            <span
              key={path}
              className="inline-flex items-center gap-1 rounded-md border border-grid bg-surface px-2 py-1 text-xs text-ink"
              title={path}
            >
              {path.split("/").pop()}
              <button
                type="button"
                onClick={() => removeAttachment(path)}
                className="rounded p-0.5 text-graphite hover:text-ink"
                aria-label={t("chat.remove_attachment")}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {crawlMode && (
        <>
          <Input
            value={crawlUrl}
            onChange={(e) => onCrawlUrlChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={t("chat.crawl_url_placeholder")}
            className={`flex-1 ${urlError ? "border-danger" : ""}`}
          />
          {urlError && (
            <div className="text-xs text-danger">{urlError}</div>
          )}
        </>
      )}

      <div className="flex items-end gap-2">
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={prompt}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={crawlMode ? t("chat.web_page_placeholder") : t("chat.db_placeholder")}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-[14px] text-ink placeholder:text-graphite outline-none leading-relaxed min-h-6 max-h-36"
        />
        <Button
          variant="primary"
          isIconOnly
          size="sm"
          onPress={handleSend}
          isDisabled={disabled || (!prompt.trim() && !(crawlMode && crawlUrl.trim()))}
          aria-label={t("chat.send")}
          className="shrink-0"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>

      {uploadError && (
        <div className="text-xs text-danger">{uploadError}</div>
      )}
    </div>
  );
}
