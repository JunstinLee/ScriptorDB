import { request } from "./core";
import type { InteractRequest, InteractByCoordsRequest, InteractResponse, ViewportSizeResponse, BrowserState, CookiesResponse, ProfilesResponse, SetCookieRequest } from "../types";
import { processSseStream } from "./stream";
import type { StreamRunEvent } from "../types";

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

export async function completeTakeover(
  sessionId: string,
  result: string,
  onEvent: (event: StreamRunEvent) => void,
  onDone: (fullOutput: string) => void,
  onError: (error: Error) => void,
): Promise<AbortController> {
  const abort = new AbortController();
  void (async () => {
    try {
      const response = await fetch("/api/browser/takeover/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, result }),
        signal: abort.signal,
      });
      await processSseStream(response, onEvent, onError, onDone);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err : new Error("Unknown error"));
    }
  })();
  return abort;
}

export async function enterHumanControl(sessionId: string): Promise<void> {
  await request("/browser/takeover/enter-human-control", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
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

// Cookie API

export async function fetchCookies(): Promise<CookiesResponse> {
  return request<CookiesResponse>("/browser/cookies");
}

export async function setCookie(req: SetCookieRequest): Promise<void> {
  await request("/browser/cookies", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function deleteCookie(name: string): Promise<void> {
  await request(`/browser/cookies/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export async function clearAllCookies(): Promise<void> {
  await request("/browser/cookies", {
    method: "DELETE",
  });
}

// Profile API

export async function fetchProfiles(): Promise<ProfilesResponse> {
  return request<ProfilesResponse>("/browser/profiles");
}

export async function saveProfile(name: string): Promise<void> {
  await request("/browser/profiles", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function loadProfile(name: string): Promise<void> {
  await request(`/browser/profiles/${encodeURIComponent(name)}/load`, {
    method: "POST",
  });
}

export async function deleteProfile(name: string): Promise<void> {
  await request(`/browser/profiles/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export async function updateProfile(name: string): Promise<void> {
  await request(`/browser/profiles/${encodeURIComponent(name)}`, {
    method: "PUT",
  });
}
