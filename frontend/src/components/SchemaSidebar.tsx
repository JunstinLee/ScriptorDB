import { useCallback, useEffect, useRef, useState } from "react";
import { Tabs } from "@heroui/react";
import { PanelRightClose, PanelRightOpen, Database, Wrench } from "lucide-react";
import type { Run, SchemaTable } from "../types";
import SchemaMap from "./SchemaMap";
import SchemaViewer from "./SchemaViewer";
import ToolsPanel from "./ToolsPanel";

interface SchemaSidebarProps {
  tables: SchemaTable[];
  schemaLoading: boolean;
  runs: Run[];
  activeSessionId: string | null;
  highlightedRunId: string | null;
  showSchemaSql: boolean;
}

export default function SchemaSidebar({
  tables,
  schemaLoading,
  runs,
  activeSessionId,
  highlightedRunId,
  showSchemaSql,
}: SchemaSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedTab, setSelectedTab] = useState("schema");
  const prevToolCountRef = useRef(0);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    if (highlightedRunId) {
      setCollapsed(false);
      setSelectedTab("tools");
    }
  }, [highlightedRunId]);

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

  if (collapsed) {
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
      <div className="flex items-center justify-between px-4 py-2.5">
        <Tabs
          selectedKey={selectedTab}
          onSelectionChange={(key: string) => setSelectedTab(key)}
          className="w-full"
        >
          <Tabs.ListContainer>
            <Tabs.List
                aria-label="Sidebar tabs"
                className="*:h-9 *:w-fit *:px-3 *:text-[11px] *:font-semibold *:uppercase *:tracking-wider"
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
              </Tabs.List>
          </Tabs.ListContainer>
        </Tabs>
        <button
          className="ml-2 shrink-0 rounded-lg p-1 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
          onClick={toggleCollapse}
          aria-label="Collapse sidebar"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {selectedTab === "schema" ? (
          <div>
            <SchemaMap tables={tables} />
            <SchemaViewer tables={tables} loading={schemaLoading} showSql={showSchemaSql} />
          </div>
        ) : (
          <div className="px-2">
            {!activeSessionId ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted">
                <p className="text-sm">No session selected</p>
              </div>
            ) : (
              <ToolsPanel runs={runs} highlightedRunId={highlightedRunId} />
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
