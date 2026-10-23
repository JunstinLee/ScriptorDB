import { useCallback, useEffect, useState } from "react";
import { Modal, Tabs } from "@heroui/react";
import { useTranslation } from "react-i18next";
import {
  Folder,
  Key,
  Languages,
  MessageSquare,
  Settings as SettingsIcon,
} from "lucide-react";
import { fetchSettings } from "../api/client";
import type { SettingsResponse, WorkspaceDetail } from "../types";
import AlertBanner from "./common/AlertBanner";
import ApiKeysTab from "./settings/ApiKeysTab";
import DefaultsTab from "./settings/DefaultsTab";
import LanguageTab from "./settings/LanguageTab";
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
  const { t } = useTranslation();
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
      setError(e instanceof Error ? e.message : t("settings.load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (isOpen) void load();
  }, [isOpen, load]);

  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={onOpenChange}>
      <Modal.Container size="lg" scroll="inside">
        <Modal.Dialog className="h-120 w-full max-h-[85vh] bg-surface sm:w-187.5 sm:max-w-187.5">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Heading className="pl-3">{t("settings.title")}</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            {error && <AlertBanner variant="error" message={error} />}
            {loading || !settings ? (
              <div className="flex h-full items-center justify-center text-sm text-muted">
                {t("settings.loading")}
              </div>
            ) : (
              <Tabs
                orientation="vertical"
                className="h-full w-full"
                defaultSelectedKey="workspaces"
              >
                <Tabs.ListContainer className="h-full w-37.5 shrink-0 bg-surface">
                  <Tabs.List
                    aria-label={t("settings.title")}
                    className="w-full bg-surface *:h-9 *:w-full *:justify-start *:px-3 *:text-start *:text-[11px] *:font-semibold *:uppercase *:tracking-wider *:text-graphite *:data-[selected=true]:text-foreground"
                  >
                    <Tabs.Tab id="workspaces">
                      <Folder className="mr-1.5 inline size-3.5 text-graphite" />
                      {t("settings.tab.workspaces")}
                      <Tabs.Indicator className="bg-foreground/5" />
                    </Tabs.Tab>
                    <Tabs.Tab id="sessions">
                      <MessageSquare className="mr-1.5 inline size-3.5 text-graphite" />
                      {t("settings.tab.sessions")}
                      <Tabs.Indicator className="bg-foreground/5" />
                    </Tabs.Tab>
                    <Tabs.Tab id="language">
                      <Languages className="mr-1.5 inline size-3.5 text-graphite" />
                      {t("settings.tab.language")}
                      <Tabs.Indicator className="bg-foreground/5" />
                    </Tabs.Tab>
                    <Tabs.Tab id="apikeys">
                      <Key className="mr-1.5 inline size-3.5 text-graphite" />
                      {t("settings.tab.api_keys")}
                      <Tabs.Indicator className="bg-foreground/5" />
                    </Tabs.Tab>
                    <Tabs.Tab id="defaults">
                      <SettingsIcon className="mr-1.5 inline size-3.5 text-graphite" />
                      {t("settings.tab.defaults")}
                      <Tabs.Indicator className="bg-foreground/5" />
                    </Tabs.Tab>
                  </Tabs.List>
                </Tabs.ListContainer>

                <Tabs.Panel className="min-w-0 flex-1 overflow-y-auto" id="workspaces">
                  <WorkspacesTab
                    activeWorkspace={activeWorkspace}
                    workspacesCount={workspacesCount}
                    onOpenPicker={onOpenWorkspacePicker}
                    onWorkspaceChanged={onWorkspaceChanged}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="min-w-0 flex-1 overflow-y-auto" id="sessions">
                  <SessionsTab
                    settings={settings}
                    onSettingsChange={setSettings}
                    showSessionIdHover={showSessionIdHover}
                    setShowSessionIdHover={setShowSessionIdHover}
                    showSchemaSql={showSchemaSql}
                    setShowSchemaSql={setShowSchemaSql}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="min-w-0 flex-1 overflow-y-auto" id="language">
                  <LanguageTab
                    settings={settings}
                    onSettingsChange={setSettings}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="min-w-0 flex-1 overflow-y-auto" id="apikeys">
                  <ApiKeysTab
                    settings={settings}
                    onSettingsChange={setSettings}
                  />
                </Tabs.Panel>
                <Tabs.Panel className="min-w-0 flex-1 overflow-y-auto" id="defaults">
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
