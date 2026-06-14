export const DEFAULT_SESSION_TITLE = "New Chat";

export function getSessionDisplayName(
  title: string | null | undefined,
): string {
  return title?.trim() || DEFAULT_SESSION_TITLE;
}
