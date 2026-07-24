import { useCallback, useEffect, useRef, useState } from "react";
import ChatInput from "./ChatInput";
import ChatMessages from "./ChatMessages";
import ModelProviderBar from "./ModelProviderBar";
import WelcomeScreen from "./WelcomeScreen";
import type { ChatMessage, Run, SchemaTable, UndoGroup, WorkspaceDetail } from "../types";
import { uploadFile } from "../api/files";
import { fetchSettings, updateSettings } from "../api/settings";
import { toast } from "@heroui/react";

interface ChatPanelProps {
  activeSessionId: string | null;
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  settingsChanged: number;
  workspace: WorkspaceDetail | null;
  tables: SchemaTable[];
  undoGroups: UndoGroup[];
  onSend: (prompt: string, attachments: string[], crawlUrl: string | null) => void;
  onNewSession: () => void;
  onRevertToHere: (groupId: number) => void;
  onHighlightRun: (runId: string) => void;
  onSelectionChange: (model: string, provider: string) => void;
}

export default function ChatPanel({
  activeSessionId,
  messages,
  runs,
  isLoading,
  settingsChanged,
  workspace,
  tables,
  undoGroups,
  onSend,
  onNewSession,
  onRevertToHere,
  onHighlightRun,
  onSelectionChange,
}: ChatPanelProps) {
  const [attachments, setAttachments] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [crawlMode, setCrawlMode] = useState(false);
  const [crawlUrl, setCrawlUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [globeMode, setGlobeMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    fetchSettings().then((s) => {
      if (mountedRef.current) setGlobeMode(s.browser_enabled);
    }).catch(() => {});
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (settingsChanged > 0) {
      fetchSettings().then((s) => {
        if (mountedRef.current) setGlobeMode(s.browser_enabled);
      }).catch(() => {});
    }
  }, [settingsChanged]);

  const removeAttachment = useCallback((path: string) => {
    setAttachments((prev) => prev.filter((p) => p !== path));
  }, []);

  const handleAttachClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
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

  const toggleGlobe = useCallback(() => {
    const next = !globeMode;
    setGlobeMode(next);
    updateSettings({ browser_enabled: next })
      .then(() => {
        toast.success(next ? "Browser control enabled" : "Browser control disabled");
      })
      .catch(() => {});
  }, [globeMode]);

  const handleUrlChange = useCallback((value: string) => {
    setCrawlUrl(value);
    if (!value.trim()) {
      setUrlError(null);
    } else {
      try {
        const normalized = value.includes("://") ? value : `https://${value}`;
        new URL(normalized);
        setUrlError(null);
      } catch {
        // keep current error state
      }
    }
  }, []);

  const wrappedOnSend = useCallback((prompt: string, atts: string[], crawlUrlParam: string | null) => {
    onSend(prompt, atts, crawlUrlParam);
    setAttachments([]);
    setUploadError(null);
    setUrlError(null);
    if (crawlMode) {
      setCrawlMode(false);
      setCrawlUrl("");
    }
  }, [onSend, crawlMode]);

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeSessionId ? (
          <ChatMessages
            messages={messages}
            runs={runs}
            isLoading={isLoading}
            undoGroups={undoGroups}
            onRevertToHere={onRevertToHere}
            onHighlightRun={onHighlightRun}
          />
        ) : (
          <WelcomeScreen
            workspace={workspace}
            tables={tables}
            onNewSession={onNewSession}
          />
        )}
      </div>

      <div className="shrink-0 bg-background px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-grid bg-surface">
          <ChatInput
            onSend={wrappedOnSend}
            disabled={isLoading}
            attachments={attachments}
            removeAttachment={removeAttachment}
            uploadError={uploadError}
            crawlMode={crawlMode}
            crawlUrl={crawlUrl}
            urlError={urlError}
            onCrawlUrlChange={handleUrlChange}
          />
          <ModelProviderBar
            settingsChanged={settingsChanged}
            onSelectionChange={onSelectionChange}
            onAttachClick={handleAttachClick}
            onFileChange={handleFileChange}
            fileInputRef={fileInputRef}
            isUploading={isUploading}
            crawlMode={crawlMode}
            onToggleCrawl={toggleCrawl}
            globeMode={globeMode}
            onToggleGlobe={toggleGlobe}
            disabled={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
