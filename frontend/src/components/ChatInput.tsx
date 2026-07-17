import { useCallback, useRef, useState } from "react";
import { Button, Input } from "@heroui/react";
import { ArrowUp, Globe, Paperclip, X } from "lucide-react";
import { uploadFile } from "../api/files";

interface ChatInputProps {
  onSend: (prompt: string, attachments: string[], crawlUrl: string | null) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [prompt, setPrompt] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [crawlMode, setCrawlMode] = useState(false);
  const [crawlUrl, setCrawlUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const isValidUrl = (url: string): boolean => {
    if (!url.trim()) return false;
    try {
      new URL(normalizeUrl(url.trim()));
      return true;
    } catch {
      return false;
    }
  };

  const handleSend = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed && attachments.length === 0) return;

    if (crawlMode) {
      if (!crawlUrl.trim()) return;
      if (!isValidUrl(crawlUrl.trim())) {
        setUrlError("Invalid URL");
        return;
      }
    }

    onSend(
      trimmed || (crawlMode ? "Analyze the web page" : ""),
      attachments,
      crawlMode ? normalizeUrl(crawlUrl.trim()) : null,
    );
    setPrompt("");
    setAttachments([]);
    setUploadError(null);
    setUrlError(null);
    if (crawlMode) {
      setCrawlMode(false);
      setCrawlUrl("");
    }
    requestAnimationFrame(() => {
      const ta = textareaRef.current;
      if (ta) {
        ta.style.height = "auto";
      }
    });
  }, [prompt, attachments, crawlMode, crawlUrl, onSend]);

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

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploadError(null);
      setIsUploading(true);
      try {
        const res = await uploadFile(file);
        setAttachments((prev) => [...prev, res.path]);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setIsUploading(false);
        e.target.value = "";
      }
    },
    [],
  );

  const removeAttachment = useCallback((path: string) => {
    setAttachments((prev) => prev.filter((p) => p !== path));
  }, []);

  const handleAttachClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const toggleCrawl = useCallback(() => {
    setCrawlMode((prev) => {
      if (prev) {
        setCrawlUrl("");
        setUrlError(null);
      }
      return !prev;
    });
  }, []);

  const handleUrlChange = useCallback((value: string) => {
    setCrawlUrl(value);
    if (!value.trim()) {
      setUrlError(null);
    } else if (urlError) {
      try {
        new URL(normalizeUrl(value.trim()));
        setUrlError(null);
      } catch {
        // keep error
      }
    }
  }, [urlError]);

  const handleUrlKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
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
                aria-label="Remove attachment"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
          className="hidden"
        />
        <button
          type="button"
          onClick={handleAttachClick}
          disabled={disabled || isUploading}
          className="shrink-0 rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink disabled:opacity-50"
          aria-label="Attach CSV or Excel file"
          title="Attach CSV or Excel file"
        >
          <Paperclip className="h-4 w-4" />
        </button>

        <button
          type="button"
          onClick={toggleCrawl}
          disabled={disabled}
          className={`shrink-0 rounded-lg p-2 transition-colors hover:bg-default/50 disabled:opacity-50 ${
            crawlMode ? "text-sapphire bg-default/30" : "text-graphite hover:text-ink"
          }`}
          aria-label="Toggle web crawl mode"
          title="Crawl a web page"
        >
          <Globe className="h-4 w-4" />
        </button>

        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={crawlMode ? "Enter a question about the web page..." : "Ask about your database..."}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-[14px] text-ink placeholder:text-graphite outline-none leading-relaxed min-h-[24px] max-h-[144px]"
        />
        <Button
          variant="primary"
          isIconOnly
          size="sm"
          onPress={handleSend}
          isDisabled={disabled || (!prompt.trim() && !(crawlMode && crawlUrl.trim()))}
          aria-label="Send"
          className="shrink-0"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>

      {crawlMode && (
        <>
          <Input
            value={crawlUrl}
            onChange={(e) => handleUrlChange(e.target.value)}
            onKeyDown={handleUrlKeyDown}
            placeholder="Enter URL to crawl..."
            className={`flex-1 ${urlError ? "border-danger" : ""}`}
          />
          {urlError && (
            <div className="text-xs text-danger">{urlError}</div>
          )}
        </>
      )}

      {uploadError && (
        <div className="text-xs text-danger">{uploadError}</div>
      )}
    </div>
  );
}
