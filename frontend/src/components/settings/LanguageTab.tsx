import { Label, ListBox, Select } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { updateSettings } from "../../api/client";
import {
  detectBrowserLocale,
  SUPPORTED_LOCALES,
  type Locale,
} from "../../i18n";
import type { SettingsResponse } from "../../types";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  zh: "简体中文",
};

const AUTO = "auto";

interface LanguageTabProps {
  settings: SettingsResponse;
  onSettingsChange: (s: SettingsResponse) => void;
}

export default function LanguageTab({
  settings,
  onSettingsChange,
}: LanguageTabProps) {
  const { t, i18n } = useTranslation();

  const handleChange = async (next: string) => {
    const choice = next === AUTO ? "" : next;
    try {
      const updated = await updateSettings({ locale: choice });
      onSettingsChange(updated);
      await i18n.changeLanguage(choice || detectBrowserLocale());
    } catch {
      // settings update failed; keep the current language
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-grid bg-surface p-3">
      <p className="text-xs text-muted">{t("settings.language.description")}</p>
      <Select
        className="w-[220px]"
        name="locale-select"
        value={settings.locale || AUTO}
        onChange={(v) => {
          if (typeof v === "string") void handleChange(v);
        }}
      >
        <Label>{t("settings.language.title")}</Label>
        <Select.Trigger>
          <Select.Value />
          <Select.Indicator />
        </Select.Trigger>
        <Select.Popover>
          <ListBox>
            <ListBox.Item id={AUTO} textValue={t("settings.language.follow_browser")}>
              <span>{t("settings.language.follow_browser")}</span>
              <ListBox.ItemIndicator />
            </ListBox.Item>
            {SUPPORTED_LOCALES.map((locale) => (
              <ListBox.Item
                key={locale}
                id={locale}
                textValue={LOCALE_LABELS[locale]}
              >
                <span>{LOCALE_LABELS[locale]}</span>
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox>
        </Select.Popover>
      </Select>
    </div>
  );
}
