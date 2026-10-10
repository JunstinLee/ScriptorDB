import { useCallback, useEffect, useState } from "react";
import { Button, Input, Label } from "@heroui/react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      setStatus({ kind: "error", message: t("settings.api_keys.empty") });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      const resp = await saveApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (!resp.ok) {
        setStatus({
          kind: "error",
          message: resp.error || t("settings.api_keys.save_failed"),
        });
        return;
      }
      setApiKey("");
      setStatus({ kind: "saved" });
      const updated = await fetchSettings();
      onSettingsChange(updated);
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : t("settings.api_keys.save_failed"),
      });
    }
  }, [apiKey, onSettingsChange, selectedProvider, t]);

  const handleTest = useCallback(async () => {
    if (!apiKey.trim()) {
      setStatus({ kind: "error", message: t("settings.api_keys.enter_to_test") });
      return;
    }
    setStatus({ kind: "saving" });
    try {
      const resp = await testApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (resp.ok) {
        setStatus({ kind: "tested", message: t("settings.api_keys.valid") });
      } else {
        setStatus({
          kind: "error",
          message: resp.error || t("settings.api_keys.test_failed"),
        });
      }
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : t("settings.api_keys.test_failed"),
      });
    }
  }, [apiKey, selectedProvider, t]);

  const handleDelete = useCallback(async () => {
    setStatus({ kind: "saving" });
    try {
      await deleteApiKey(selectedProvider);
      setStatus({ kind: "saved", message: t("settings.api_keys.removed") });
      const updated = await fetchSettings();
      onSettingsChange(updated);
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : t("settings.api_keys.delete_failed"),
      });
    }
  }, [onSettingsChange, selectedProvider, t]);

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
          ? t("settings.api_keys.configured")
          : t("settings.api_keys.unset")}
      </p>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="apikeys-api-key" className="text-xs text-graphite">
          {t("settings.api_keys.label")}
        </Label>
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
            aria-label={
              showKey ? t("settings.api_keys.hide") : t("settings.api_keys.show")
            }
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
          {status.kind === "saving"
            ? t("settings.api_keys.saving")
            : t("settings.api_keys.save")}
        </Button>
        <Button
          variant="secondary"
          onPress={() => void handleTest()}
          isDisabled={status.kind === "saving" || !apiKey.trim()}
        >
          {t("settings.api_keys.test")}
        </Button>
        {isConfigured && (
          <Button
            variant="tertiary"
            onPress={() => void handleDelete()}
            isDisabled={status.kind === "saving"}
          >
            {t("settings.api_keys.remove")}
          </Button>
        )}
      </div>
    </div>
  );
}
