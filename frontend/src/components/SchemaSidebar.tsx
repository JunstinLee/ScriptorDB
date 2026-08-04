import { useCallback, useEffect, useRef, useState, type Key } from "react";
import { Tabs } from "@heroui/react";
import { PanelRightClose, PanelRightOpen, Database, Wrench, List, Map, Globe } from "lucide-react";
import type { BrowserState, Run, SchemaTable, BrowserProfileItem, CookieInfo } from "../types";
import SchemaMap from "./SchemaMap";
import SchemaViewer from "./SchemaViewer";
import ToolsPanel from "./ToolsPanel";
import BrowserProfilePanel from "./BrowserProfilePanel";
import CookieViewer from "./CookieViewer";

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
  const [collapsed, setCollapsed] = useState(false);
  const [selectedTab, setSelectedTab] = useState("schema");
  const [schemaView, setSchemaView] = useState<"map" | "list">("map");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const prevToolCountRef = useRef(0);

  const effectiveCollapsed = collapsed && !highlightedRunId;
  const effectiveSelectedTab = highlightedRunId ? "tools" : selectedTab;

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    prevToolCountRef.current = 0;
  }, [activeSessionId]);

  useEffect(() => {
    const currentCount = runs.reduce((sum, r) => sum + r.tool_invocations.length, 0);
    if (currentCount > prevToolCountRef.current) {
      setCollapsed(false);
      setSelectedTab("tools");
    }
    prevToolCountRef.current = currentCount;
  }, [runs]);

  const handleTableClick = useCallback(
    (name: string) => {
      setSelectedTable(name);
      setSchemaView("list");
    },
    [],
  );

  if (effectiveCollapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center gap-3 border-l py-3">
        <button
          className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
          onClick={toggleCollapse}
          aria-label="Expand schema sidebar"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-[360px] shrink-0 flex-col border-l">
      <div className="flex items-center gap-2 border-b border-grid px-3 py-2">
        <Tabs
          selectedKey={effectiveSelectedTab}
          onSelectionChange={(key: Key) => setSelectedTab(String(key))}
          className="w-auto"
        >
          <Tabs.ListContainer>
            <Tabs.List
              aria-label="Sidebar tabs"
              className="gap-0 *:h-8 *:w-fit *:px-2.5 *:text-[11px] *:font-semibold *:uppercase *:tracking-wider"
            >
              <Tabs.Tab id="schema">
                <Database className="mr-1.5 inline size-3.5 text-graphite" />
                Schema
                <Tabs.Indicator className="bg-cobalt" />
              </Tabs.Tab>
              <Tabs.Tab id="tools">
                <Wrench className="mr-1.5 inline size-3.5 text-graphite" />
                Tools
                <Tabs.Indicator className="bg-cobalt" />
              </Tabs.Tab>
              {browserEnabled && (
                <Tabs.Tab id="profiles">
                  <Globe className="mr-1.5 inline size-3.5 text-graphite" />
                  Profiles
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
            aria-label="Collapse sidebar"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto py-2">
        {effectiveSelectedTab === "schema" ? (
          <div className="flex flex-1 flex-col gap-2 min-h-0">
            <div className="flex items-center gap-1 px-3">
              <button
                type="button"
                onClick={() => setSchemaView("map")}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                  schemaView === "map"
                    ? "bg-cobalt/10 text-cobalt"
                    : "text-muted hover:text-ink hover:bg-default/50"
                }`}
                aria-pressed={schemaView === "map"}
              >
                <Map className="size-3" />
                Map
              </button>
              <button
                type="button"
                onClick={() => setSchemaView("list")}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                  schemaView === "list"
                    ? "bg-cobalt/10 text-cobalt"
                    : "text-muted hover:text-ink hover:bg-default/50"
                }`}
                aria-pressed={schemaView === "list"}
              >
                <List className="size-3" />
                List
              </button>
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
                <p className="text-sm">No session selected</p>
              </div>
            ) : (
              <ToolsPanel runs={runs} highlightedRunId={highlightedRunId} browserState={browserState} browserLoading={browserLoading} onViewBrowser={onViewBrowser} />
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
