export function formatWorkspacePath(path: string | null | undefined): string {
  if (!path) return "";
  const idx = path.indexOf(".config");
  return idx >= 0 ? path.slice(idx) : path;
}
