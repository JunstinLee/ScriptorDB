import { Check } from "lucide-react";
import { Label, ListBox, Select } from "@heroui/react";
import type { ProviderInfo } from "../../types";

interface ProviderSelectProps {
  providers: ProviderInfo[];
  value: string;
  onChange: (v: string) => void;
  configuredSet?: Set<string>;
  label?: string;
  name?: string;
}

export default function ProviderSelect({
  providers,
  value,
  onChange,
  configuredSet,
  label = "Provider",
  name = "provider-select",
}: ProviderSelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Select
        className="w-full"
        name={name}
        placeholder="Select provider"
        value={value}
        onChange={(v) => {
          if (typeof v === "string") onChange(v);
        }}
      >
        <Label>{label}</Label>
        <Select.Trigger>
          <Select.Value />
          <Select.Indicator />
        </Select.Trigger>
        <Select.Popover>
          <ListBox>
            {providers.map((p) => (
              <ListBox.Item key={p.name} id={p.name} textValue={p.name}>
                <span className="flex items-center gap-2">
                  <span>{p.name}</span>
                  {configuredSet?.has(p.name) && (
                    <Check className="size-3.5 text-success" />
                  )}
                </span>
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox>
        </Select.Popover>
      </Select>
    </div>
  );
}
