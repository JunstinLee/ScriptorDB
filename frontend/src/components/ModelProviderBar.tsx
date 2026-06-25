import { Label, ListBox, Select } from "@heroui/react";
import { PROVIDERS } from "../constants";
import { useModelSelector } from "../hooks/useModelSelector";
import type { ModelEntry } from "../types";

interface ModelProviderBarProps {
  settingsChanged: number;
  onSelectionChange: (model: string, provider: string) => void;
}

export default function ModelProviderBar({
  settingsChanged,
  onSelectionChange,
}: ModelProviderBarProps) {
  const {
    provider,
    setProvider,
    model,
    setModel,
    models,
    loadingModels,
    formatModelLabel,
  } = useModelSelector(settingsChanged, onSelectionChange);

  return (
    <div className="flex items-center gap-3 px-4 py-2">
      <div className="flex items-center gap-2">
        <Label className="text-xs text-graphite">Provider</Label>
        <Select
          className="w-[120px]"
          name="model-provider"
          placeholder="Default"
          value={provider}
          onChange={(v) => {
            if (typeof v === "string") setProvider(v);
          }}
        >
          <Select.Trigger>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Select.Popover>
            <ListBox>
              <ListBox.Item key="" id="" textValue="Default">
                Default
              </ListBox.Item>
              {PROVIDERS.map((p) => (
                <ListBox.Item key={p} id={p} textValue={p}>
                  {p}
                </ListBox.Item>
              ))}
            </ListBox>
          </Select.Popover>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <Label className="text-xs text-graphite">Model</Label>
        <Select
          className="w-[200px]"
          name="model-select"
          placeholder="Default"
          value={model}
          onChange={(v) => {
            if (typeof v === "string") {
              setModel(v);
              onSelectionChange(v, provider);
            }
          }}
          isDisabled={loadingModels && models.length === 0}
        >
          <Select.Trigger>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Select.Popover>
            <ListBox>
              <ListBox.Item key="" id="" textValue="Default">
                Default
              </ListBox.Item>
              {models.map((entry) => (
                <ListBox.Item
                  key={entry.provider_specific_id}
                  id={entry.provider_specific_id}
                  textValue={formatModelLabel(entry)}
                >
                  {formatModelLabel(entry)}
                </ListBox.Item>
              ))}
            </ListBox>
          </Select.Popover>
        </Select>
      </div>
    </div>
  );
}
