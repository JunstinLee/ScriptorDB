import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { PanelRightClose, PanelRightOpen, Database, Wrench, Globe } from "lucide-react";
import type { BrowserState, Run, SchemaTable, BrowserProfileItem, CookieInfo } from "../types";
import SchemaViewer from "./SchemaViewer";
import ToolsPanel from "./ToolsPanel";
import BrowserProfilePanel from "./BrowserProfilePanel";
import CookieViewer from "./CookieViewer";

const RAIL_BASE =
  "rounded-lg text-muted transition-colors hover:bg-default/50 hover:text-foreground focus-cobalt";

const TAB_BASE =
  "relative flex items-center gap-1.5 border-b-2 px-2.5 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors focus-cobalt";

type TabId = "schema" | "tools" | "profiles";

interface SchemaSidebarProps {
  tables: SchemaTable[];
  schemaLoading: boolean;
  runs: Run[];
  activeSessionId: string | null;
  highlightedRunId: string | null;
  showSchemaSql: boolean;
  browserState: BrowserState | null;
  browserLoading: boolean;
  browserEnabled: boolean;
  onViewBrowser: () => void;
  profiles?: BrowserProfileItem[];
  profilesLoading?: boolean;
  cookies?: CookieInfo[];
  cookiesLoading?: boolean;
  onSaveProfile?: (name: string) => void;
  onLoadProfile?: (name: string) => void;
  onDeleteProfile?: (name: string) => void;
  onUpdateProfile?: (name: string) => void;
  onDeleteCookie?: (name: string) => void;
  onClearCookies?: () => void;
  onRefreshCookies?: () => void;
}

export default function SchemaSidebar({
  tables,
  schemaLoading,
  runs,
  activeSessionId,
  highlightedRunId,
  showSchemaSql,
  browserState,
  browserLoading,
  browserEnabled,
  onViewBrowser,
  profiles,
  profilesLoading,
  cookies,
  cookiesLoading,
  onSaveProfile,
  onLoadProfile,
  onDeleteProfile,
  onUpdateProfile,
  onDeleteCookie,
  onClearCookies,
  onRefreshCookies,
}: SchemaSidebarProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(
    () => window.matchMedia("(max-width: 1100px)").matches,
  );
  const [selectedTab, setSelectedTab] = useState<TabId>("schema");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const toolCount = runs.reduce((sum, run) => sum + run.tool_invocations.length, 0);

  // 一级 tab 的唯一定义：展开态与折叠轨道共用
  const TABS = [
    {
      id: "schema",
      icon: Database,
      labelKey: "schema.tab.schema",
      badge: tables.length,
      enabled: true,
    },
    {
      id: "tools",
      icon: Wrench,
      labelKey: "schema.tab.tools",
      badge: toolCount,
      enabled: true,
    },
    {
      id: "profiles",
      icon: Globe,
      labelKey: "schema.tab.profiles",
      badge: profiles?.length ?? 0,
      enabled: browserEnabled,
    },
  ] as const;

  const visibleTabs = TABS.filter((tab) => tab.enabled);
  const activeTab: TabId = visibleTabs.some((tab) => tab.id === selectedTab)
    ? selectedTab
    : (visibleTabs[0]?.id ?? "schema");

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleTableClick = useCallback((name: string) => {
    setSelectedTable(name);
  }, []);

  const expandToTab = useCallback((tab: TabId) => {
    setSelectedTab(tab);
    setCollapsed(false);
  }, []);

  // 窄屏只在跨进来时折叠一次，跨回宽屏不自动展开
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1100px)");
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) setCollapsed(true);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // 高亮某一轮时一次性切到 tools 面板，之后控制权交还用户
  useEffect(() => {
    if (!highlightedRunId) return;
    setSelectedTab("tools");
    setCollapsed(false);
  }, [highlightedRunId]);

  const handleTablistKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const ids = visibleTabs.map((tab) => tab.id);
    const current = ids.indexOf(activeTab);
    const step = e.key === "ArrowRight" ? 1 : -1;
    const next = (current + step + ids.length) % ids.length;
    setSelectedTab(ids[next]);
    tabRefs.current[next]?.focus();
  };

  if (collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-1 border-l py-3">
        <button
          className={`${RAIL_BASE} p-1.5`}
          onClick={toggleCollapse}
          aria-label={t("schema.expand_aria")}
          title={t("schema.expand_aria")}
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            className={`${RAIL_BASE} relative flex w-10 flex-col items-center gap-0.5 py-1.5`}
            onClick={() => expandToTab(tab.id)}
            aria-label={t(tab.labelKey)}
            title={t(tab.labelKey)}
          >
            <tab.icon className="size-4" />
            <span className="font-mono text-[10px] leading-none">{tab.badge}</span>
            {activeTab === tab.id && (
              <span
                className="absolute right-1 top-1 size-0.5 rounded-full bg-accent"
                aria-hidden
              />
            )}
          </button>
        ))}
      </aside>
    );
  }

  return (
    <aside className="flex w-90 shrink-0 flex-col border-l">
      <div className="flex shrink-0 items-center border-b border-default pl-1 pr-2">
        <div
          role="tablist"
          aria-label={t("schema.tabs_aria")}
          className="flex items-center"
          onKeyDown={handleTablistKeyDown}
        >
          {visibleTabs.map((tab, index) => {
            const active = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                ref={(el) => {
                  tabRefs.current[index] = el;
                }}
                role="tab"
                aria-selected={active}
                tabIndex={active ? 0 : -1}
                onClick={() => setSelectedTab(tab.id)}
                className={`${TAB_BASE} ${
                  active
                    ? "border-accent text-accent"
                    : "border-transparent text-muted hover:text-foreground"
                }`}
              >
                <tab.icon className="size-3.5" />
                {t(tab.labelKey)}
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <button
            className="rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors focus-cobalt"
            onClick={toggleCollapse}
            aria-label={t("sidebar.collapse")}
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto py-2">
        {activeTab === "schema" ? (
          <div className="flex flex-1 flex-col gap-2 min-h-0">
            <div className="flex items-center px-3">
              <span className="text-[11px] font-semibold text-muted">
                {t("schema.tables_count", { count: tables.length })}
              </span>
            </div>

            <SchemaViewer
              tables={tables}
              loading={schemaLoading}
              showSql={showSchemaSql}
              selectedTable={selectedTable}
              onTableClick={handleTableClick}
            />
          </div>
        ) : activeTab === "tools" ? (
          <div className="px-3">
            {!activeSessionId ? (
              <p className="py-6 text-[13px] leading-relaxed text-muted">
                {t("schema.no_session")}
              </p>
            ) : (
              <ToolsPanel runs={runs} highlightedRunId={highlightedRunId} browserState={browserState} browserLoading={browserLoading} onViewBrowser={onViewBrowser} />
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3 px-3">
            <BrowserProfilePanel
              profiles={profiles ?? []}
              loading={profilesLoading ?? false}
              onSave={onSaveProfile ?? (() => {})}
              onLoad={onLoadProfile ?? (() => {})}
              onDelete={onDeleteProfile ?? (() => {})}
              onUpdate={onUpdateProfile ?? (() => {})}
              browserLaunched={browserState?.launched ?? false}
            />
            <CookieViewer
              cookies={cookies ?? []}
              loading={cookiesLoading ?? false}
              currentUrl={browserState?.url ?? ""}
              browserLaunched={browserState?.launched ?? false}
              onDeleteCookie={onDeleteCookie ?? (() => {})}
              onClearAll={onClearCookies ?? (() => {})}
              onRefresh={onRefreshCookies ?? (() => {})}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
