import { useRef } from "react";
import { useTranslation } from "react-i18next";

interface MainTabBarProps {
  activeMainTab: "chat" | "browser";
  onTabChange: (tab: "chat" | "browser") => void;
  browserLoading: boolean;
}

const MAIN_TABS = ["chat", "browser"] as const;

const TAB_BASE =
  "relative flex items-center gap-1.5 border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors focus-cobalt";

export default function MainTabBar({
  activeMainTab,
  onTabChange,
  browserLoading,
}: MainTabBarProps) {
  const { t } = useTranslation();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const current = MAIN_TABS.indexOf(activeMainTab);
    const step = e.key === "ArrowRight" ? 1 : -1;
    const next = (current + step + MAIN_TABS.length) % MAIN_TABS.length;
    onTabChange(MAIN_TABS[next]);
    tabRefs.current[next]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={t("app.tabs_aria")}
      onKeyDown={handleKeyDown}
      className="flex shrink-0 items-center border-b border-default bg-background px-4"
    >
      {MAIN_TABS.map((tab, index) => {
        const active = activeMainTab === tab;
        return (
          <button
            key={tab}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onTabChange(tab)}
            className={`${TAB_BASE} ${
              active
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t(tab === "chat" ? "app.tab.chat" : "app.tab.browser")}
            {tab === "browser" && browserLoading && (
              <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
            )}
          </button>
        );
      })}
    </div>
  );
}
