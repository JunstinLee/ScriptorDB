import { Monitor, MessageSquare } from "lucide-react";

interface MainTabBarProps {
  activeMainTab: "chat" | "browser";
  onTabChange: (tab: "chat" | "browser") => void;
  browserLoading: boolean;
}

export default function MainTabBar({
  activeMainTab,
  onTabChange,
  browserLoading,
}: MainTabBarProps) {
  return (
    <div className="flex shrink-0 items-center border-b border-grid bg-background px-4">
      <button
        onClick={() => onTabChange("chat")}
        className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
          activeMainTab === "chat"
            ? "border-accent text-accent"
            : "border-transparent text-muted hover:text-foreground"
        }`}
      >
        <MessageSquare className="size-3.5" />
        Chat
      </button>

      <button
        onClick={() => onTabChange("browser")}
        className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
          activeMainTab === "browser"
            ? "border-accent text-accent"
            : "border-transparent text-muted hover:text-foreground"
        }`}
      >
        <Monitor className="size-3.5" />
        Browser
        {browserLoading && (
          <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
        )}
      </button>
    </div>
  );
}
