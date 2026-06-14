import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Input,
  Label,
  ListBox,
  Modal,
  Select,
  Switch,
  Tabs,
} from "@heroui/react";
import {
  Check,
  Eye,
  EyeOff,
  Key,
  MessageSquare,
  Settings as SettingsIcon,
  Trash2,
} from "lucide-react";
import {
  deleteApiKey,
  deleteSession,
  fetchModels,
  fetchRecommendedModels,
  fetchSettings,
  listSessions,
  saveApiKey,
  testApiKey,
  updateSettings,
} from "../api/client";
import type {
  SessionListItem,
  SettingsResponse,
} from "../types";
import { getSessionDisplayName } from "../utils/display";

interface SettingsModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSessionsChanged?: () => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
}

export default function SettingsModal({
  isOpen,
  onOpenChange,
  onSessionsChanged,
  showSessionIdHover,
  setShowSessionIdHover,
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
        <Modal.Dialog className="sm:max-w-[640px] max-h-[85vh]">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Icon className="bg-accent-soft text-accent-soft-foreground">
              <SettingsIcon className="size-5" />
            </Modal.Icon>
            <Modal.Heading>Settings</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            {error && (
              <div className="mb-3 rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
                {error}
              </div>
            )}
            {loading || !settings ? (
              <div className="flex items-center justify-center py-12 text-sm text-muted">
                Loading…
              </div>
            ) : (
              <Tabs className="w-full" defaultSelectedKey="sessions">
                <Tabs.ListContainer>
                  <Tabs.List
                    aria-label="Settings"
                    className="w-fit *:h-9 *:w-fit *:px-3 *:text-sm *:font-normal"
                  >
                    <Tabs.Tab id="sessions">
                      <MessageSquare className="mr-1.5 inline size-4" />
                      Sessions
                      <Tabs.Indicator />
                    </Tabs.Tab>
                    <Tabs.Tab id="apikeys">
                      <Key className="mr-1.5 inline size-4" />
                      API Keys
                      <Tabs.Indicator />
                    </Tabs.Tab>
                    <Tabs.Tab id="defaults">
                      <SettingsIcon className="mr-1.5 inline size-4" />
                      Default Models
                      <Tabs.Indicator />
                    </Tabs.Tab>
                  </Tabs.List>
                </Tabs.ListContainer>

                <Tabs.Panel className="pt-4" id="sessions">
                  <SessionsTab
                    settings={settings}
                    onSettingsChange={setSettings}
                    onSessionsChanged={onSessionsChanged}
                    showSessionIdHover={showSessionIdHover}
                    setShowSessionIdHover={setShowSessionIdHover}
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

interface SessionsTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
  onSessionsChanged?: () => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
}

function SessionsTab({
  settings,
  onSettingsChange,
  onSessionsChanged,
  showSessionIdHover,
  setShowSessionIdHover,
}: SessionsTabProps) {
  const [items, setItems] = useState<SessionListItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [toggling, setToggling] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listSessions();
      setItems(res.sessions);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggleAutoRestore = useCallback(
    async (next: boolean) => {
      setToggling(true);
      try {
        const updated = await updateSettings({ auto_restore_sessions: next });
        onSettingsChange(updated);
      } catch (e) {
        console.error(e);
      } finally {
        setToggling(false);
      }
    },
    [onSettingsChange],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between rounded-lg border p-3">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm font-medium">
            Auto-restore sessions on restart
          </Label>
          <p className="text-xs text-muted">
            When enabled, the server re-loads previous sessions on startup and
            this UI restores your last active session.
          </p>
        </div>
        <Switch
          isSelected={settings.auto_restore_sessions}
          onChange={(v) => void handleToggleAutoRestore(v)}
          isDisabled={toggling}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-3">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm font-medium">
            Show session ID on hover
          </Label>
          <p className="text-xs text-muted">
            When enabled, hovering over a session name shows the underlying
            session ID as a tooltip.
          </p>
        </div>
        <Switch
          isSelected={showSessionIdHover}
          onChange={(v) => void setShowSessionIdHover(v)}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">History</h3>
          <Button
            size="sm"
            variant="ghost"
            onPress={() => void refresh()}
            isDisabled={loading}
          >
            Refresh
          </Button>
        </div>

        {items === null ? (
          <div className="py-4 text-center text-sm text-muted">Loading…</div>
        ) : items.length === 0 ? (
          <div className="py-4 text-center text-sm text-muted">
            No sessions yet.
          </div>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {items.map((s) => {
              const displayName = getSessionDisplayName(s.title);
              return (
                <li
                  key={s.session_id}
                  className="flex items-center gap-3 rounded-lg border bg-surface/50 px-3 py-2"
                >
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span
                      className="truncate text-sm font-medium"
                      title={showSessionIdHover ? s.session_id : displayName}
                    >
                      {displayName}
                    </span>
                    <span className="text-xs text-muted">
                      {s.message_count} message{s.message_count === 1 ? "" : "s"} ·
                      last active {formatRelative(s.last_access)}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    isIconOnly
                    aria-label={`Delete ${displayName}`}
                    onPress={async () => {
                      try {
                        await deleteSession(s.session_id);
                        await refresh();
                        onSessionsChanged?.();
                      } catch (e) {
                        console.error(e);
                      }
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

interface ApiKeysTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
}

function ApiKeysTab({ settings, onSettingsChange }: ApiKeysTabProps) {
  const [selectedProvider, setSelectedProvider] = useState<string>(
    settings.llm_provider,
  );
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState<{
    kind: "idle" | "saving" | "saved" | "error" | "tested";
    message?: string;
  }>({ kind: "idle" });

  useEffect(() => {
    setSelectedProvider(settings.llm_provider);
  }, [settings.llm_provider]);

  const configuredSet = new Set(settings.providers_with_keys);

  const handleSave = useCallback(async () => {
    if (!apiKey.trim()) {
      setStatus({ kind: "error", message: "API key cannot be empty" });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      const resp = await saveApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (!resp.ok) {
        setStatus({ kind: "error", message: resp.error || "Save failed" });
        return;
      }
      setApiKey("");
      setStatus({ kind: "saved" });
      const updated = await fetchSettings();
      onSettingsChange(updated);
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Save failed",
      });
    }
  }, [apiKey, onSettingsChange, selectedProvider]);

  const handleTest = useCallback(async () => {
    if (!apiKey.trim()) {
      setStatus({ kind: "error", message: "Enter an API key to test" });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      const resp = await testApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (resp.ok) {
        setStatus({ kind: "tested", message: "API key is valid" });
      } else {
        setStatus({ kind: "error", message: resp.error || "Test failed" });
      }
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Test failed",
      });
    }
  }, [apiKey, selectedProvider]);

  const handleDelete = useCallback(async () => {
    setStatus({ kind: "saving" });
    try {
      await deleteApiKey(selectedProvider);
      setStatus({ kind: "saved", message: "API key removed" });
      const updated = await fetchSettings();
      onSettingsChange(updated);
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Delete failed",
      });
    }
  }, [onSettingsChange, selectedProvider]);

  const isConfigured = configuredSet.has(selectedProvider);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Select
          className="w-full"
          name="apikeys-provider"
          placeholder="Select provider"
          value={selectedProvider}
          onChange={(v) => {
            if (typeof v === "string") setSelectedProvider(v);
            setStatus({ kind: "idle" });
          }}
        >
          <Label>Provider</Label>
          <Select.Trigger>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Select.Popover>
            <ListBox>
              {settings.providers.map((p) => (
                <ListBox.Item key={p.name} id={p.name} textValue={p.name}>
                  <span className="flex items-center gap-2">
                    <span>{p.name}</span>
                    {configuredSet.has(p.name) && (
                      <Check className="size-3.5 text-success" />
                    )}
                  </span>
                  <ListBox.ItemIndicator />
                </ListBox.Item>
              ))}
            </ListBox>
          </Select.Popover>
        </Select>
        <p className="text-xs text-muted">
          {isConfigured
            ? "API key is configured. Enter a new value to replace it."
            : "No API key is currently set for this provider."}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="apikeys-api-key">API Key</Label>
        <div className="flex gap-2">
          <Input
            id="apikeys-api-key"
            name="api_key"
            className="flex-1"
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              setStatus({ kind: "idle" });
            }}
            placeholder="sk-…"
            autoComplete="off"
          />
          <Button
            variant="ghost"
            isIconOnly
            aria-label={showKey ? "Hide key" : "Show key"}
            onPress={() => setShowKey((v) => !v)}
          >
            {showKey ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </Button>
        </div>
      </div>

      {status.kind === "error" && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          {status.message}
        </div>
      )}
      {status.kind === "tested" && (
        <div className="rounded-lg border border-success/40 bg-success/10 p-2 text-sm text-success">
          {status.message}
        </div>
      )}
      {status.kind === "saved" && status.message && (
        <div className="rounded-lg border border-success/40 bg-success/10 p-2 text-sm text-success">
          {status.message}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onPress={() => void handleSave()}
          isDisabled={status.kind === "saving" || !apiKey.trim()}
        >
          {status.kind === "saving" ? "Saving…" : "Save"}
        </Button>
        <Button
          variant="secondary"
          onPress={() => void handleTest()}
          isDisabled={status.kind === "saving" || !apiKey.trim()}
        >
          Test
        </Button>
        {isConfigured && (
          <Button
            variant="tertiary"
            onPress={() => void handleDelete()}
            isDisabled={status.kind === "saving"}
          >
            Remove stored key
          </Button>
        )}
      </div>
    </div>
  );
}

interface DefaultsTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
}

function DefaultsTab({ settings, onSettingsChange }: DefaultsTabProps) {
  const [selectedProvider, setSelectedProvider] = useState<string>(
    settings.llm_provider,
  );
  const [models, setModels] = useState<string[]>([]);
  const [pickedModel, setPickedModel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const currentDefault = settings.default_models[selectedProvider] ?? null;

  const loadModels = useCallback(async (provider: string) => {
    setLoading(true);
    setError(null);
    setPickedModel(null);
    try {
      let resp = await fetchRecommendedModels(provider);
      let list = resp.models;
      if (list.length === 0) {
        resp = await fetchModels(provider);
        list = resp.models;
      }
      setModels(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load models");
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadModels(selectedProvider);
  }, [loadModels, selectedProvider]);

  const handleSetDefault = useCallback(
    async (model: string) => {
      setSaving(true);
      setStatus(null);
      try {
        const updated = await updateSettings({
          default_model: model,
          default_model_provider: selectedProvider,
        });
        onSettingsChange(updated);
        setStatus(`Default model set to ${model}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to save");
      } finally {
        setSaving(false);
      }
    },
    [onSettingsChange, selectedProvider],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Select
          className="w-full"
          name="defaults-provider"
          placeholder="Select provider"
          value={selectedProvider}
          onChange={(v) => {
            if (typeof v === "string") setSelectedProvider(v);
            setStatus(null);
            setError(null);
          }}
        >
          <Label>Provider</Label>
          <Select.Trigger>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Select.Popover>
            <ListBox>
              {settings.providers.map((p) => (
                <ListBox.Item key={p.name} id={p.name} textValue={p.name}>
                  {p.name}
                  <ListBox.ItemIndicator />
                </ListBox.Item>
              ))}
            </ListBox>
          </Select.Popover>
        </Select>
        <p className="text-xs text-muted">
          Current default model:{" "}
          <span className="font-mono text-foreground">
            {currentDefault || "(none)"}
          </span>
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label id="defaults-model-label">
          Set default model for {selectedProvider}
        </Label>
        {loading ? (
          <div className="py-3 text-sm text-muted">Loading models…</div>
        ) : models.length === 0 ? (
          <div className="py-3 text-sm text-muted">
            No models available. Configure an API key first.
          </div>
        ) : (
          <ListBox
            aria-labelledby="defaults-model-label"
            selectionMode="single"
            selectedKeys={pickedModel ? [pickedModel] : []}
            onSelectionChange={(keys) => {
              const v = (keys as { values?: () => Iterable<string> }).values
                ? [...((keys as { values: () => Iterable<string> }).values())][0]
                : [...(keys as Set<string>)][0];
              if (typeof v === "string") setPickedModel(v);
            }}
            className="max-h-64 overflow-y-auto rounded-lg border"
          >
            {models.map((m) => (
              <ListBox.Item
                key={m}
                id={m}
                textValue={m}
                className="data-[selected=true]:bg-accent/15"
              >
                <div className="flex flex-1 items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs">{m}</span>
                  {m === currentDefault && (
                    <Check className="size-3.5 text-success" />
                  )}
                </div>
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          {error}
        </div>
      )}
      {status && (
        <div className="rounded-lg border border-success/40 bg-success/10 p-2 text-sm text-success">
          {status}
        </div>
      )}

      <div className="flex justify-end">
        <Button
          variant="primary"
          isDisabled={loading || models.length === 0 || saving}
          onPress={async () => {
            const defaultPick =
              pickedModel ?? currentDefault ?? models[0] ?? "";
            const pick = window.prompt(
              `Enter a model ID for ${selectedProvider} (one of: ${models.slice(0, 5).join(", ")}${models.length > 5 ? "…" : ""})`,
              defaultPick,
            );
            if (pick) await handleSetDefault(pick.trim());
          }}
        >
          {saving ? "Saving…" : "Set default"}
        </Button>
      </div>
    </div>
  );
}

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - then);
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
