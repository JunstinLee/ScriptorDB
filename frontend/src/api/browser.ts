import { request } from "./core";
import type { BrowserState } from "../types";

/** 获取当前浏览器状态快照 */
export async function fetchBrowserState(): Promise<BrowserState> {
  return request<BrowserState>("/browser/state");
}

/** 构造截图图片 URL（用于 <img src>） */
export function getScreenshotUrl(): string {
  return `/api/browser/screenshot?t=${Date.now()}`;
}
