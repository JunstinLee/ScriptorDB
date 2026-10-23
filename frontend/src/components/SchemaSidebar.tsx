import { useCallback, useState, type Key } from "react";
import { useTranslation } from "react-i18next";
import { Tabs } from "@heroui/react";
import { PanelRightClose, PanelRightOpen, Database, Wrench, List, Map, Globe } from "lucide-react";
import type { BrowserState, Run, SchemaTable, BrowserProfileItem, CookieInfo } from "../types";
import SchemaMap from "./SchemaMap";
import SchemaViewer from "./SchemaViewer";
import ToolsPanel from "./ToolsPanel";
import BrowserProfilePanel from "./BrowserProfilePanel";
import CookieViewer from "./CookieViewer";

const RAIL_BUTTON =
  "rounded-lg p-1.5 text-muted transition-colors hover:bg-default/50 hover:text-foreground";

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
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [selectedTab, setSelectedTab] = useState("schema");
  const [schemaView, setSchemaView] = useState<"map" | "list">("map");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  const effectiveCollapsed = collapsed && !highlightedRunId;
  const effectiveSelectedTab = highlightedRunId ? "tools" : selectedTab;

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleTableClick = useCallback(
    (name: string) => {
      setSelectedTable(name);
      setSchemaView("list");
    },
    [],
  );

  const expandToTab = useCallback((tab: string) => {
    setSelectedTab(tab);
    setCollapsed(false);
  }, []);

  if (effectiveCollapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-1 border-l py-3">
        <button
          className={RAIL_BUTTON}
          onClick={toggleCollapse}
          aria-label={t("schema.expand_aria")}
          title={t("schema.expand_aria")}
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <div className="my-1 h-px w-6 bg-grid" aria-hidden />
        <button
          className={RAIL_BUTTON}
          onClick={() => expandToTab("schema")}
          aria-label={t("schema.tab.schema")}
          title={t("schema.tab.schema")}
        >
          <Database className="h-4 w-4" />
        </button>
        <button
          className={RAIL_BUTTON}
          onClick={() => expandToTab("tools")}
          aria-label={t("schema.tab.tools")}
          title={t("schema.tab.tools")}
        >
          <Wrench className="h-4 w-4" />
        </button>
        {browserEnabled && (
          <button
            className={RAIL_BUTTON}
            onClick={() => expandToTab("profiles")}
            aria-label={t("schema.tab.profiles")}
            title={t("schema.tab.profiles")}
          >
            <Globe className="h-4 w-4" />
          </button>
        )}
      </aside>
    );
  }

  return (
    <aside
      className="flex w-[360px] shrink-0 flex-col border-l"
      onMouseEnter={() => setSidebarHovered(true)}
      onMouseLeave={() => setSidebarHovered(false)}
    >
      <div className="flex items-center gap-2 border-b border-grid px-3 py-2">
        <Tabs
          selectedKey={effectiveSelectedTab}
          onSelectionChange={(key: Key) => setSelectedTab(String(key))}
          className="w-auto"
        >
          <Tabs.ListContainer>
            <Tabs.List
              aria-label={t("schema.tabs_aria")}
              className="gap-0 *:h-8 *:w-fit *:px-2.5 *:text-[11px] *:font-semibold *:uppercase *:tracking-wider"
            >
              <Tabs.Tab id="schema">
                <Database className="mr-1.5 inline size-3.5 text-graphite" />
                {t("schema.tab.schema")}
                <Tabs.Indicator className="bg-cobalt" />
              </Tabs.Tab>
              <Tabs.Tab id="tools">
                <Wrench className="mr-1.5 inline size-3.5 text-graphite" />
                {t("schema.tab.tools")}
                <Tabs.Indicator className="bg-cobalt" />
              </Tabs.Tab>
              {browserEnabled && (
                <Tabs.Tab id="profiles">
                  <Globe className="mr-1.5 inline size-3.5 text-graphite" />
                  {t("schema.tab.profiles")}
                  <Tabs.Indicator className="bg-cobalt" />
                </Tabs.Tab>
              )}
            </Tabs.List>
          </Tabs.ListContainer>
        </Tabs>
        <div className="ml-auto flex items-center gap-1">
          <button
            className="rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
            onClick={toggleCollapse}
            aria-label={t("sidebar.collapse")}
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto py-2">
        {effectiveSelectedTab === "schema" ? (
          <div className="flex flex-1 flex-col gap-2 min-h-0">
            <div className="flex items-center px-3">
              <Tabs
                selectedKey={schemaView}
                onSelectionChange={(key: Key) =>
                  setSchemaView(String(key) === "list" ? "list" : "map")
                }
                className="w-auto"
              >
                <Tabs.ListContainer>
                  <Tabs.List
                    aria-label={t("schema.view_aria")}
                    className="gap-0 *:h-7 *:w-fit *:px-2 *:text-[11px] *:font-semibold *:uppercase *:tracking-wider"
                  >
                    <Tabs.Tab id="map">
                      <Map className="mr-1 inline size-3 text-graphite" />
                      {t("schema.view.map")}
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                    <Tabs.Tab id="list">
                      <List className="mr-1 inline size-3 text-graphite" />
                      {t("schema.view.list")}
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                  </Tabs.List>
                </Tabs.ListContainer>
              </Tabs>
            </div>

            {schemaView === "map" ? (
              <SchemaMap
                tables={tables}
                selectedTable={selectedTable}
                onTableClick={handleTableClick}
              />
            ) : (
              <SchemaViewer
                tables={tables}
                loading={schemaLoading}
                showSql={showSchemaSql}
                selectedTable={selectedTable}
                onTableClick={handleTableClick}
              />
            )}
          </div>
        ) : effectiveSelectedTab === "tools" ? (
          <div className="px-2">
            {!activeSessionId ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted">
                <p className="text-sm">{t("schema.no_session")}</p>
              </div>
            ) : (
              <ToolsPanel runs={runs} highlightedRunId={highlightedRunId} sidebarHovered={sidebarHovered} browserState={browserState} browserLoading={browserLoading} onViewBrowser={onViewBrowser} />
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
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
