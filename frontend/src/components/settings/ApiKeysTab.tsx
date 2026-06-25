import { useCallback, useEffect, useState } from "react";
import { Button, Input, Label } from "@heroui/react";
import { Eye, EyeOff } from "lucide-react";
import {
  deleteApiKey,
  fetchSettings,
  saveApiKey,
  testApiKey,
} from "../../api/client";
import type { SettingsResponse } from "../../types";
import AlertBanner from "../common/AlertBanner";
import ProviderSelect from "../common/ProviderSelect";

interface ApiKeysTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
}

export default function ApiKeysTab({ settings, onSettingsChange }: ApiKeysTabProps) {
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
  const isConfigured = configuredSet.has(selectedProvider);

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

  return (
    <div className="flex flex-col gap-4">
      <ProviderSelect
        providers={settings.providers}
        value={selectedProvider}
        onChange={(v) => {
          setSelectedProvider(v);
          setStatus({ kind: "idle" });
        }}
        configuredSet={configuredSet}
        name="apikeys-provider"
      />
      <p className="text-xs text-muted">
        {isConfigured
          ? "API key is configured. Enter a new value to replace it."
          : "No API key is currently set for this provider."}
      </p>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="apikeys-api-key" className="text-xs text-graphite">API Key</Label>
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
        <AlertBanner variant="error" message={status.message ?? ""} />
      )}
      {status.kind === "tested" && (
        <AlertBanner variant="success" message={status.message ?? ""} />
      )}
      {status.kind === "saved" && status.message && (
        <AlertBanner variant="success" message={status.message} />
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
