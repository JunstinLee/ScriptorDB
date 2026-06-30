const BASE = "/api";

export function getImageUrl(fileId: string): string {
  return `${BASE}/files/${encodeURIComponent(fileId)}`;
}

export function downloadImage(fileId: string, filename?: string): void {
  const url = getImageUrl(fileId);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || fileId;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
