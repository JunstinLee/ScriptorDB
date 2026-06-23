const BASE = "/api";

export class ApiError extends Error {
  status: number;
  body: string;
  code: string | null;

  constructor(status: number, body: string) {
    super(`HTTP ${status}: ${body}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = extractErrorCode(body);
  }
}

export class WorkspaceNotSelectedError extends ApiError {
  constructor(body: string) {
    super(409, body);
    this.name = "WorkspaceNotSelectedError";
  }
}

function extractErrorCode(body: string): string | null {
  if (!body) return null;
  try {
    const obj = JSON.parse(body) as { code?: unknown; detail?: unknown };
    if (typeof obj.code === "string") return obj.code;
    if (typeof obj.detail === "string") return obj.detail;
  } catch {
    // body is not JSON
  }
  return null;
}

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    const code = extractErrorCode(text);
    if (res.status === 409 && code === "WORKSPACE_NOT_SELECTED") {
      throw new WorkspaceNotSelectedError(text);
    }
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}
