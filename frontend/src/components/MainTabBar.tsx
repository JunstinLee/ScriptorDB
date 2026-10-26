import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();

  return (
    <div className="flex shrink-0 items-center border-b border-default bg-background px-4">
      <button
        onClick={() => onTabChange("chat")}
        className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
          activeMainTab === "chat"
            ? "border-accent text-accent"
            : "border-transparent text-muted hover:text-foreground"
        }`}
      >
        {t("app.tab.chat")}
      </button>

      <button
        onClick={() => onTabChange("browser")}
        className={`relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
          activeMainTab === "browser"
            ? "border-accent text-accent"
            : "border-transparent text-muted hover:text-foreground"
        }`}
      >
        {t("app.tab.browser")}
        {browserLoading && (
          <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
        )}
      </button>
    </div>
  );
}
