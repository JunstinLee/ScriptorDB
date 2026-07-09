import { ApiError, WorkspaceNotSelectedError } from "./core";

const BASE = "/api";

export interface UploadFileResponse {
  filename: string;
  path: string;
}

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

export async function uploadFile(file: File): Promise<UploadFileResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/files/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    if (res.status === 409 && text.includes("WORKSPACE_NOT_SELECTED")) {
      throw new WorkspaceNotSelectedError(text);
    }
    throw new ApiError(res.status, text);
  }

  return res.json() as Promise<UploadFileResponse>;
}
