import type { FilterActionType } from "./filters";

/** 浏览器单次操作记录 */
export interface BrowserAction {
  tool: string;
  detail: string;
  timestamp: string;
  success: boolean;
}

/** SSE 推送的实时浏览器操作事件 */
export interface BrowserActionEvent {
  type: "browser_action";
  run_id: string;
  tool: string;
  selector: string;
  coords: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  success: boolean;
  detail: string;
  timestamp: string;
}

/** 浏览器页面历史条目 */
export interface BrowserHistoryEntry {
  url: string;
  title: string;
  timestamp: string;
}

/** 浏览器完整状态快照（对应 GET /api/browser/state 返回值） */
export interface BrowserState {
  launched: boolean;
  url: string | null;
  title: string | null;
  screenshot_available: boolean;
  /** 任务结束后是否已调度自动关闭（倒计时中） */
  idle_close_active: boolean;
  /** 距自动关闭的剩余秒数（未调度时为 0） */
  idle_close_remaining: number;
  actions: BrowserAction[];
  history: BrowserHistoryEntry[];
}

export interface InteractRequest {
  action:
    | "click"
    | "fill"
    | "press_key"
    | "scroll"
    | "navigate"
    | "go_back"
    | "go_forward"
    | FilterActionType;
  selector?: string;
  value?: string;
  scroll_pixels?: number;
  target?: string;
  values?: string;
  submit?: boolean;
}

export interface InteractByCoordsRequest {
  x: number;
  y: number;
  viewport_width: number;
  viewport_height: number;
}

export interface InteractResponse {
  ok: boolean;
  action: string;
  selector: string;
  detail: string;
}

export interface TakeoverCompleteRequest {
  session_id: string;
  result: string;
}

export interface TakeoverEnterControlRequest {
  session_id: string;
}

export interface TakeoverCancelRequest {
  session_id: string;
  run_id?: string;
}

export interface ViewportSizeResponse {
  width: number;
  height: number;
}

export interface CookieInfo {
  name: string;
  domain: string;
  path: string;
  expires: number | null;
  http_only: boolean;
  secure: boolean;
  same_site: string;
}

export interface CookiesResponse {
  cookies: CookieInfo[];
  count: number;
  current_url: string;
}

export interface BrowserProfileItem {
  name: string;
  domain: string;
  cookie_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProfilesResponse {
  profiles: BrowserProfileItem[];
}

export interface SaveProfileRequest {
  name: string;
}

export interface SetCookieRequest {
  name: string;
  value: string;
  domain?: string;
  path?: string;
  secure?: boolean;
  http_only?: boolean;
  same_site?: string;
  expires?: number;
}
