import { useState, useRef, useCallback } from "react";
import { AlertTriangle, X, MousePointer, Type, Keyboard, ArrowUpDown, Globe, Loader2 } from "lucide-react";
import type { HumanTakeoverRequestEvent, BrowserActionEvent } from "../types";
import { interactBrowser, interactByCoords } from "../api/browser";

interface HumanTakeoverPanelProps {
  event: HumanTakeoverRequestEvent | null;
  onComplete: (result: string) => void;
  onCancel: () => void;
  screenshotSrc: string;
  onScreenshotRefresh: () => void;
  actions: BrowserActionEvent[];
  onClearActions: () => void;
}

type InteractMode = "click" | "fill" | "press_key" | "scroll" | "navigate";

function TakeoverBanner({ reason, currentUrl, onCancel }: { reason: string; currentUrl: string; onCancel: () => void }) {
  return (
    <div className="flex items-start justify-between rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3">
      <div className="flex items-start gap-3 min-w-0">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-500" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
            Agent 已暂停 — 需要人工操作
          </p>
          <p className="mt-1 text-[13px] text-amber-600/80 dark:text-amber-300/70 truncate">
            原因：{reason}
          </p>
          <p className="mt-0.5 text-[12px] text-muted truncate font-mono">
            当前页面：{currentUrl}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onCancel}
        className="ml-2 shrink-0 rounded-lg p-1.5 text-muted hover:bg-foreground/10 transition-colors"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

function InteractToolbar({ mode, onModeChange }: { mode: InteractMode; onModeChange: (m: InteractMode) => void }) {
  const modes: { key: InteractMode; icon: React.ReactNode; label: string }[] = [
    { key: "click", icon: <MousePointer className="size-4" />, label: "点击" },
    { key: "fill", icon: <Type className="size-4" />, label: "输入" },
    { key: "press_key", icon: <Keyboard className="size-4" />, label: "按键" },
    { key: "scroll", icon: <ArrowUpDown className="size-4" />, label: "滚动" },
    { key: "navigate", icon: <Globe className="size-4" />, label: "导航" },
  ];

  return (
    <div className="flex gap-1.5">
      {modes.map((m) => (
        <button
          key={m.key}
          type="button"
          onClick={() => onModeChange(m.key)}
          className={
            "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors " +
            (mode === m.key
              ? "bg-accent text-white shadow-sm"
              : "bg-surface/60 text-muted hover:bg-surface hover:text-foreground")
          }
        >
          {m.icon}
          {m.label}
        </button>
      ))}
    </div>
  );
}

const KEY_OPTIONS = ["Enter", "Tab", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Backspace", "Delete"];

function ClickOverlay({
  active,
  onCoordsClick,
  loading,
  screenshotSrc,
}: {
  active: boolean;
  onCoordsClick: (x: number, y: number, vw: number, vh: number) => void;
  loading: boolean;
  screenshotSrc: string;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [ripple, setRipple] = useState<{ x: number; y: number; id: number } | null>(null);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLImageElement>) => {
      if (!active || !imgRef.current) return;
      const rect = imgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const displayW = rect.width;
      const displayH = rect.height;
      setRipple({ x, y, id: Date.now() });
      onCoordsClick(x, y, displayW, displayH);
    },
    [active, onCoordsClick],
  );

  return (
    <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface">
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/60">
          <Loader2 className="size-6 animate-spin text-accent" />
        </div>
      )}
      <img
        ref={imgRef}
        src={screenshotSrc}
        alt="页面截图"
        className="h-full w-full object-contain"
        style={{ cursor: active ? "crosshair" : "default" }}
        onClick={handleClick}
      />
      {ripple && (
        <div
          key={ripple.id}
          className="absolute z-10 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/60 animate-ping pointer-events-none"
          style={{ left: ripple.x, top: ripple.y }}
        />
      )}
    </div>
  );
}

function ActionResult({ actions, onClear }: { actions: BrowserActionEvent[]; onClear: () => void }) {
  const recent = actions.slice(-5).reverse();

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-medium text-muted">最近操作</span>
        {actions.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="text-[11px] text-muted hover:text-foreground transition-colors"
          >
            清空
          </button>
        )}
      </div>
      {recent.length === 0 ? (
        <p className="text-[12px] text-muted/60">暂无操作</p>
      ) : (
        <div className="max-h-24 space-y-1 overflow-y-auto">
          {recent.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-lg bg-surface/50 px-2 py-1 text-[12px]"
            >
              <span className={a.success ? "text-green-600" : "text-red-500"}>{a.success ? "OK" : "ERR"}</span>
              <span className="text-muted font-mono">{a.tool}</span>
              <span className="truncate text-foreground/70">{a.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function HumanTakeoverPanel({
  event,
  onComplete,
  onCancel,
  screenshotSrc,
  onScreenshotRefresh,
  actions,
  onClearActions,
}: HumanTakeoverPanelProps) {
  const [mode, setMode] = useState<InteractMode>("click");
  const [selector, setSelector] = useState("");
  const [value, setValue] = useState("");
  const [navUrl, setNavUrl] = useState("");
  const [pressKey, setPressKey] = useState("Enter");
  const [scrollPixels, setScrollPixels] = useState(300);
  const [resultText, setResultText] = useState("");
  const [loading, setLoading] = useState(false);

  if (!event) return null;

  async function handleInteract(
    action: InteractMode,
    extra?: Record<string, unknown>,
  ) {
    setLoading(true);
    try {
      if (action === "click") {
        await interactBrowser({ action: "click", selector, value, scroll_pixels: undefined });
      } else if (action === "fill") {
        await interactBrowser({ action: "fill", selector, value, scroll_pixels: undefined });
      } else if (action === "press_key") {
        await interactBrowser({ action: "press_key", value: extra?.key as string ?? pressKey, scroll_pixels: undefined });
      } else if (action === "scroll") {
        await interactBrowser({ action: "scroll", scroll_pixels: extra?.pixels as number ?? scrollPixels });
      } else if (action === "navigate") {
        await interactBrowser({ action: "navigate", value: extra?.url as string ?? navUrl, scroll_pixels: undefined });
      }
    } catch (err) {
      console.error("interact error:", err);
    } finally {
      setLoading(false);
      onScreenshotRefresh();
    }
  }

  async function handleCoordsClick(x: number, y: number, vw: number, vh: number) {
    setLoading(true);
    try {
      await interactByCoords(x, y, vw, vh);
    } catch (err) {
      console.error("coords click error:", err);
    } finally {
      setLoading(false);
      onScreenshotRefresh();
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <TakeoverBanner
        reason={event.reason}
        currentUrl={event.current_url}
        onCancel={onCancel}
      />

      <InteractToolbar mode={mode} onModeChange={setMode} />

      {mode === "click" && (
        <ClickOverlay
          active={true}
          onCoordsClick={handleCoordsClick}
          loading={loading}
          screenshotSrc={screenshotSrc}
        />
      )}

      {mode !== "click" && (
        <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface">
          <img
            src={screenshotSrc}
            alt="页面截图"
            className="h-full w-full object-contain"
          />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/60">
              <Loader2 className="size-6 animate-spin text-accent" />
            </div>
          )}
        </div>
      )}

      {mode === "fill" && (
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <label className="text-[12px] font-medium text-muted">CSS Selector</label>
            <input
              type="text"
              value={selector}
              onChange={(e) => setSelector(e.target.value)}
              placeholder="#username"
              className="w-full rounded-lg border border-grid bg-surface px-3 py-1.5 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-[12px] font-medium text-muted">Value</label>
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="输入内容"
              className="w-full rounded-lg border border-grid bg-surface px-3 py-1.5 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            type="button"
            onClick={() => handleInteract("fill")}
            disabled={loading || !selector}
            className="shrink-0 rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
          >
            执行
          </button>
        </div>
      )}

      {mode === "press_key" && (
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <label className="text-[12px] font-medium text-muted">按键</label>
            <select
              value={pressKey}
              onChange={(e) => setPressKey(e.target.value)}
              className="w-full rounded-lg border border-grid bg-surface px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {KEY_OPTIONS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => handleInteract("press_key")}
            disabled={loading}
            className="shrink-0 rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
          >
            执行
          </button>
        </div>
      )}

      {mode === "scroll" && (
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <label className="text-[12px] font-medium text-muted">滚动像素</label>
            <input
              type="number"
              value={scrollPixels}
              onChange={(e) => setScrollPixels(Number(e.target.value))}
              className="w-full rounded-lg border border-grid bg-surface px-3 py-1.5 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => handleInteract("scroll", { pixels: -Math.abs(scrollPixels) })}
              disabled={loading}
              className="rounded-lg bg-surface/80 px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface disabled:opacity-50 transition-colors"
            >
              Up
            </button>
            <button
              type="button"
              onClick={() => handleInteract("scroll", { pixels: Math.abs(scrollPixels) })}
              disabled={loading}
              className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
            >
              Down
            </button>
          </div>
        </div>
      )}

      {mode === "navigate" && (
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <label className="text-[12px] font-medium text-muted">URL</label>
            <input
              type="text"
              value={navUrl}
              onChange={(e) => setNavUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg border border-grid bg-surface px-3 py-1.5 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            type="button"
            onClick={() => handleInteract("navigate")}
            disabled={loading || !navUrl}
            className="shrink-0 rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
          >
            Go
          </button>
        </div>
      )}

      <ActionResult actions={actions} onClear={onClearActions} />

      <div className="border-t border-grid pt-3 space-y-2">
        <div className="space-y-1">
          <label className="text-[12px] font-medium text-muted">描述你做了什么：</label>
          <textarea
            value={resultText}
            onChange={(e) => setResultText(e.target.value)}
            placeholder="已使用用户名 user@example.com 登录，通过了验证码"
            rows={2}
            className="w-full resize-none rounded-lg border border-grid bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div className="flex justify-between">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-grid px-4 py-1.5 text-sm font-medium text-muted hover:bg-surface transition-colors"
          >
            取消接管
          </button>
          <button
            type="button"
            onClick={() => onComplete(resultText || "用户完成操作")}
            disabled={loading}
            className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
          >
            完成并恢复 Agent
          </button>
        </div>
      </div>
    </div>
  );
}
