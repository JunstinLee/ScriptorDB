import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Globe, Search, Paperclip } from "lucide-react";
import { Switch } from "@heroui/react";
import { PROVIDERS } from "../constants";
import { useModelSelector } from "../hooks/useModelSelector";

interface ModelProviderBarProps {
  settingsChanged: number;
  onSelectionChange: (model: string, provider: string) => void;
  onAttachClick: () => void;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isUploading: boolean;
  crawlMode: boolean;
  onToggleCrawl: () => void;
  globeMode: boolean;
  onToggleGlobe: () => void;
  disabled: boolean;
}

export default function ModelProviderBar({
  settingsChanged,
  onSelectionChange,
  onAttachClick,
  onFileChange,
  fileInputRef,
  isUploading,
  crawlMode,
  onToggleCrawl,
  globeMode,
  onToggleGlobe,
  disabled,
}: ModelProviderBarProps) {
  const {
    provider,
    setProvider,
    model,
    setModel,
    models,
    loadingModels,
  } = useModelSelector(settingsChanged, onSelectionChange);

  const [popoverOpen, setPopoverOpen] = useState(false);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const updatePopoverPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const popoverWidth = 360;
    const gap = 8;

    let right = window.innerWidth - rect.right;

    if (right + popoverWidth > window.innerWidth) {
      right = window.innerWidth - popoverWidth - 8;
    }
    if (right < 0) right = 8;

    const bottom = window.innerHeight - (rect.top - gap);
    setPopoverStyle({
      position: "fixed",
      right: `${right}px`,
      bottom: `${bottom}px`,
      zIndex: 100,
    });
  }, []);

  useEffect(() => {
    if (!popoverOpen) return;
    updatePopoverPosition();

    const handleMouseDown = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        setPopoverOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPopoverOpen(false);
    };
    const handleResize = () => updatePopoverPosition();
    const handleScroll = () => updatePopoverPosition();

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResize);
    window.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [popoverOpen, updatePopoverPosition]);

  const handlePopoverToggle = useCallback(() => {
    setPopoverOpen((prev) => !prev);
  }, []);

  const handleProviderSelect = useCallback(
    (p: string) => {
      setProvider(p);
    },
    [setProvider],
  );

  const handleModelSelect = useCallback(
    (m: string) => {
      setModel(m);
      onSelectionChange(m, provider);
      setPopoverOpen(false);
    },
    [provider, setModel, onSelectionChange],
  );

  const displayProvider = provider || "default";
  const activeModel = model
    ? models.find((e) => e.provider_specific_id === model)
    : null;
  const displayModel = activeModel
    ? activeModel.display_name || activeModel.provider_specific_id
    : model || "default";

  return (
    <div className="relative flex items-center gap-3 px-3 py-2">
      <div className="flex items-center gap-1.5">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={onFileChange}
          className="hidden"
        />
        <button
          type="button"
          onClick={onAttachClick}
          disabled={disabled || isUploading}
          className="shrink-0 rounded-lg p-2 text-graphite transition-colors hover:bg-default/50 hover:text-ink disabled:opacity-50"
          aria-label="Attach CSV or Excel file"
          title="Attach CSV or Excel file"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onToggleCrawl}
          disabled={disabled}
          className={`shrink-0 rounded-lg p-2 transition-colors hover:bg-default/50 disabled:opacity-50 ${
            crawlMode ? "text-sapphire bg-default/30" : "text-graphite hover:text-ink"
          }`}
          aria-label="Toggle web crawl mode"
          title="Crawl a web page"
        >
          <Search className="h-4 w-4" />
        </button>
        <span className="shrink-0 rounded-lg p-2 flex items-center gap-1.5">
          <Globe className="h-4 w-4 text-graphite" />
          <Switch
            isSelected={globeMode}
            onChange={onToggleGlobe}
            isDisabled={disabled}
            size="sm"
            aria-label="Toggle globe mode"
          >
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
          </Switch>
        </span>
      </div>

      {/* Right: engine status */}
      <div className="ml-auto">
        <button
          ref={triggerRef}
          type="button"
          onClick={handlePopoverToggle}
          aria-label="Change model"
          className="group flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-grid/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-cobalt" />
          <span className="text-graphite transition-colors group-hover:text-ink">
            {displayProvider}
          </span>
          <span className="text-grid">/</span>
          <span className="max-w-[200px] truncate font-mono text-[12px] text-graphite transition-colors group-hover:text-ink">
            {displayModel}
          </span>
        </button>
      </div>

      {/* Two-pane popover (via Portal) */}
      {popoverOpen &&
        createPortal(
          <div
            ref={popoverRef}
            role="dialog"
            aria-label="Select model"
            style={popoverStyle}
            className="popover-animate w-[360px] overflow-hidden rounded-2xl border border-grid bg-surface shadow-lg"
          >
            <div className="flex h-[240px]">
              {/* Provider pane */}
              <div className="w-[120px] shrink-0 overflow-y-auto border-r border-grid">
                <button
                  type="button"
                  onClick={() => handleProviderSelect("")}
                  className={`flex w-full items-center px-3 py-2 text-left text-[12px] transition-colors ${
                    !provider
                      ? "bg-cobalt/8 text-cobalt"
                      : "text-ink hover:bg-grid/50"
                  }`}
                >
                  default
                </button>
                {PROVIDERS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => handleProviderSelect(p)}
                    className={`flex w-full items-center px-3 py-2 text-left text-[12px] transition-colors ${
                      provider === p
                        ? "bg-cobalt/8 text-cobalt"
                        : "text-ink hover:bg-grid/50"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {/* Model pane */}
              <div className="flex-1 overflow-y-auto">
                {!provider ? (
                  <div className="flex h-full items-center justify-center text-[12px] text-graphite">
                    Select a provider
                  </div>
                ) : loadingModels ? (
                  <div className="flex h-full items-center justify-center text-[12px] text-graphite">
                    Loading models…
                  </div>
                ) : models.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-[12px] text-graphite">
                    No models available
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => handleModelSelect("")}
                      className={`flex w-full items-center px-3 py-2 text-left text-[12px] transition-colors ${
                        !model
                          ? "bg-cobalt/8 text-cobalt"
                          : "text-ink hover:bg-grid/50"
                      }`}
                    >
                      default
                    </button>
                    {models.map((entry) => (
                      <button
                        key={entry.provider_specific_id}
                        type="button"
                        onClick={() => handleModelSelect(entry.provider_specific_id)}
                        className={`flex w-full items-center px-3 py-2 text-left transition-colors ${
                          model === entry.provider_specific_id
                            ? "bg-cobalt/8 text-cobalt"
                            : "text-ink hover:bg-grid/50"
                        }`}
                      >
                        <span className="font-mono text-[12px]">
                          {entry.display_name || entry.provider_specific_id}
                        </span>
                      </button>
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
