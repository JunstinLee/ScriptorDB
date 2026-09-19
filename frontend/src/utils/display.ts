import { t } from "../i18n";

export function getSessionDisplayName(
  title: string | null | undefined,
): string {
  return title?.trim() || t("session.default_title");
}

export function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - then);
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return t("session.relative.just_now");
    if (minutes < 60) return t("session.relative.minutes", { count: minutes });
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return t("session.relative.hours", { count: hours });
    const days = Math.floor(hours / 24);
    if (days < 30) return t("session.relative.days", { count: days });
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
