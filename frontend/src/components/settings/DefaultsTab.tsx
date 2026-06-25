import { useCallback, useEffect, useState } from "react";
import { Button, Label, ListBox } from "@heroui/react";
import { Check } from "lucide-react";
import {
  fetchModels,
  fetchRecommendedModels,
  updateSettings,
} from "../../api/client";
import type { SettingsResponse } from "../../types";
import AlertBanner from "../common/AlertBanner";
import ProviderSelect from "../common/ProviderSelect";

interface DefaultsTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
}

export default function DefaultsTab({ settings, onSettingsChange }: DefaultsTabProps) {
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
      <ProviderSelect
        providers={settings.providers}
        value={selectedProvider}
        onChange={(v) => {
          if (typeof v === "string") {
            setSelectedProvider(v);
            setStatus(null);
            setError(null);
          }
        }}
        name="defaults-provider"
      />
      <p className="text-xs text-muted">
        Current default model:{" "}
        <span className="font-mono text-foreground">
          {currentDefault || "(none)"}
        </span>
      </p>

      <div className="flex flex-col gap-1.5">
        <Label id="defaults-model-label" className="text-xs text-graphite">
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
            className="max-h-64 overflow-y-auto rounded-lg border border-grid"
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

      {error && <AlertBanner variant="error" message={error} />}
      {status && <AlertBanner variant="success" message={status} />}

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
