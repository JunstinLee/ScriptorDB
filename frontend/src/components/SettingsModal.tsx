import { useCallback, useEffect, useState } from "react";
import { Modal, Tabs } from "@heroui/react";
import {
  Folder,
  Key,
  MessageSquare,
  Settings as SettingsIcon,
} from "lucide-react";
import { fetchSettings } from "../api/client";
import type { SettingsResponse, WorkspaceDetail } from "../types";
import AlertBanner from "./common/AlertBanner";
import ApiKeysTab from "./settings/ApiKeysTab";
import DefaultsTab from "./settings/DefaultsTab";
import SessionsTab from "./settings/SessionsTab";
import WorkspacesTab from "./settings/WorkspacesTab";

interface SettingsModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
  showSchemaSql: boolean;
  setShowSchemaSql: (v: boolean) => void;
  activeWorkspace: WorkspaceDetail | null;
  workspacesCount: number;
  onWorkspaceChanged: () => void;
  onOpenWorkspacePicker: () => void;
}

export default function SettingsModal({
  isOpen,
  onOpenChange,
  showSessionIdHover,
  setShowSessionIdHover,
  showSchemaSql,
  setShowSchemaSql,
  activeWorkspace,
  workspacesCount,
  onWorkspaceChanged,
  onOpenWorkspacePicker,
}: SettingsModalProps) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSettings();
      setSettings(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) void load();
  }, [isOpen, load]);

  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={onOpenChange}>
      <Modal.Container size="lg" scroll="inside">
        <Modal.Dialog className="sm:max-w-[640px] max-h-[85vh] min-w-[480px] min-h-[360px] bg-surface">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Icon className="bg-accent-soft text-accent-soft-foreground">
              <SettingsIcon className="size-5" />
            </Modal.Icon>
            <Modal.Heading>Settings</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            {error && <AlertBanner variant="error" message={error} />}
            {loading || !settings ? (
              <div className="flex items-center justify-center py-12 text-sm text-muted">
                Loading…
              </div>
            ) : (
              <Tabs className="w-full" defaultSelectedKey="workspaces">
                <Tabs.ListContainer>
                  <Tabs.List
                    aria-label="Settings"
                    className="w-fit *:h-9 *:w-fit *:px-3 *:text-[11px] *:font-semibold *:uppercase *:tracking-wider"
                  >
                    <Tabs.Tab id="workspaces">
                      <Folder className="mr-1.5 inline size-3.5 text-graphite" />
                      Workspaces
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                    <Tabs.Tab id="sessions">
                      <MessageSquare className="mr-1.5 inline size-3.5 text-graphite" />
                      Sessions
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                    <Tabs.Tab id="apikeys">
                      <Key className="mr-1.5 inline size-3.5 text-graphite" />
                      API Keys
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                    <Tabs.Tab id="defaults">
                      <SettingsIcon className="mr-1.5 inline size-3.5 text-graphite" />
                      Default Models
                      <Tabs.Indicator className="bg-cobalt" />
                    </Tabs.Tab>
                  </Tabs.List>
                </Tabs.ListContainer>

                <Tabs.Panel className="pt-4" id="workspaces">
                  <WorkspacesTab
                    activeWorkspace={activeWorkspace}
                    workspacesCount={workspacesCount}
                    onOpenPicker={onOpenWorkspacePicker}
                    onWorkspaceChanged={onWorkspaceChanged}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="pt-4" id="sessions">
                  <SessionsTab
                    settings={settings}
                    onSettingsChange={setSettings}
                    showSessionIdHover={showSessionIdHover}
                    setShowSessionIdHover={setShowSessionIdHover}
                    showSchemaSql={showSchemaSql}
                    setShowSchemaSql={setShowSchemaSql}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="pt-4" id="apikeys">
                  <ApiKeysTab
                    settings={settings}
                    onSettingsChange={setSettings}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="pt-4" id="defaults">
                  <DefaultsTab
                    settings={settings}
                    onSettingsChange={setSettings}
                  />
                </Tabs.Panel>
              </Tabs>
            )}
          </Modal.Body>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
