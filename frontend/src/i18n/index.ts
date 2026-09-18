import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import zh from "./locales/zh.json";

export const SUPPORTED_LOCALES = ["en", "zh"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

const resources = {
  en: { translation: en },
  zh: { translation: zh },
};

export function detectBrowserLocale(): Locale {
  const language = typeof navigator === "undefined" ? "en" : navigator.language;
  return language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

void i18n.use(initReactI18next).init({
  resources,
  lng: detectBrowserLocale(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export default i18n;

export function t(key: string, params?: Record<string, string | number>): string {
  return i18n.t(key, params);
}
