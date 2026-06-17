import { useCallback, useState } from "react";
import { Tabs } from "@heroui/react";
import { PanelRightClose, PanelRightOpen, Database, Wrench } from "lucide-react";
import type { Run, SchemaTable } from "../types";
import SchemaViewer from "./SchemaViewer";
import ToolsPanel from "./ToolsPanel";

interface SchemaSidebarProps {
  tables: SchemaTable[];
  schemaLoading: boolean;
  runs: Run[];
  activeSessionId: string | null;
}

export default function SchemaSidebar({
  tables,
  schemaLoading,
  runs,
  activeSessionId,
}: SchemaSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedTab, setSelectedTab] = useState("schema");

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

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
      <div className="flex items-center justify-between border-b px-4 py-3">
        <Tabs
          selectedKey={selectedTab}
          onSelectionChange={(key: string) => setSelectedTab(key)}
          className="w-full"
        >
          <Tabs.ListContainer>
            <Tabs.List aria-label="Sidebar tabs">
              <Tabs.Tab id="schema">
                <Database className="inline h-3.5 w-3.5 mr-1" />
                Schema
                <Tabs.Indicator />
              </Tabs.Tab>
              <Tabs.Tab id="tools">
                <Wrench className="inline h-3.5 w-3.5 mr-1" />
                Tools
                <Tabs.Indicator />
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
          <SchemaViewer tables={tables} loading={schemaLoading} />
        ) : (
          <div className="px-2">
            {!activeSessionId ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted">
                <p className="text-sm">请先选择会话</p>
              </div>
            ) : (
              <ToolsPanel runs={runs} />
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
