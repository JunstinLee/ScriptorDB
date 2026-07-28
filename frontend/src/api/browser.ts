import { request } from "./core";
import type { InteractRequest, InteractByCoordsRequest, InteractResponse, TakeoverCompleteRequest, ViewportSizeResponse, BrowserState } from "../types";

export async function fetchBrowserState(): Promise<BrowserState> {
  return request<BrowserState>("/browser/state");
}

export function getScreenshotUrl(): string {
  return `/api/browser/screenshot?t=${Date.now()}`;
}

export async function interactBrowser(req: InteractRequest): Promise<InteractResponse> {
  return request<InteractResponse>("/browser/interact", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function interactByCoords(x: number, y: number, vw: number, vh: number): Promise<InteractResponse> {
  const body: InteractByCoordsRequest = { x, y, viewport_width: vw, viewport_height: vh };
  return request<InteractResponse>("/browser/interact/coords", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function completeTakeover(sessionId: string, result: string): Promise<void> {
  const body: TakeoverCompleteRequest = { session_id: sessionId, result };
  await request("/browser/takeover/complete", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function cancelTakeover(sessionId: string): Promise<void> {
  await request("/browser/takeover/cancel", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getViewportSize(): Promise<ViewportSizeResponse> {
  return request<ViewportSizeResponse>("/browser/viewport-size");
}
