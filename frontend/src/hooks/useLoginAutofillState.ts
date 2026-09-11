import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCredentialStatus } from "../api/loginCredentials";
import type {
  ExtraCandidate,
  ExtraPlacement,
  LoginFieldInfo,
  LoginFormPayload,
} from "../types";

/** 账号槽位兜底：与后端 browser/autofill.py 的 _TEXT_INPUT_TYPES 对齐 */
const TEXT_INPUT_TYPES: Record<string, true> = {
  "": true,
  text: true,
  email: true,
  tel: true,
  search: true,
  url: true,
  number: true,
};

/** 账号槽位下标：role=username 优先，否则第一个可填 text 类 input（对齐 _match_username_field） */
function accountSlotOrder(fields: LoginFieldInfo[]): number {
  const usernameIdx = fields.findIndex((f) => f.role === "username");
  if (usernameIdx >= 0) return usernameIdx;
  return fields.findIndex(
    (f) =>
      (f.tag ?? "").toLowerCase() === "input" &&
      TEXT_INPUT_TYPES[(f.type ?? "").toLowerCase()] === true &&
      f.role !== "password" &&
      f.role !== "otp",
  );
}

/**
 * 登录凭证状态（01/03 共享，BrowserWorkspace 挂载处唯一消费点）。
 *
 * 展示由【loginForm 是否出现 + 本地已配置布尔】派生，不依赖会话型
 * login_flow_status SSE（后端事件为旁路/AI 侧，不驱动 UI，避免首次登录
 * 无事件 / 保存后需重登的时序 bug）。
 *
 * `configured` 三态：null=未知（首次 site-status 查询在途）、
 * true/false=已确认。UI 对 null 不渲染采集面板，避免查询在途闪烁。
 */
export interface LoginAutofillState {
  site: string;
  url: string;
  /** null=未知（site-status 查询在途）；true/false=已确认 */
  configured: boolean | null;
  /** 当前登录页可作第三项（extra）的候选，携带 DOM 序与落位 */
  fieldCandidates: ExtraCandidate[];
  /** 保存/删除成功后由面板回调调用，本地翻转已配置布尔 */
  setConfigured: (value: boolean) => void;
}

export function useLoginAutofillState(
  loginForm: LoginFormPayload | null,
): LoginAutofillState {
  const loginUrl = loginForm?.url ?? "";
  const site = useMemo(() => {
    try {
      const u = new URL(loginUrl);
      return u.hostname.toLowerCase();
    } catch {
      return "";
    }
  }, [loginUrl]);

  // null=未知（在途）；进入登录页查一次 site-status；登录页消失不清 configured
  const [configured, setConfiguredState] = useState<boolean | null>(null);

  useEffect(() => {
    if (!site || !loginUrl) {
      return;
    }
    let cancelled = false;
    setConfiguredState(null);
    void fetchCredentialStatus(loginUrl)
      .then((status) => {
        if (!cancelled) setConfiguredState(status.configured);
      })
      .catch(() => {
        // 网络/后端不可用：回到未知（不误判未配置），面板由父组件裁决
        if (!cancelled) setConfiguredState(null);
      });
    return () => {
      cancelled = true;
    };
  }, [site, loginUrl]);

  // 第三项候选：unknown 角色且非 hidden/checkbox/radio；order 保留 DOM 文档序，
  // placement 由账号/密码槽位区间派生（账号与密码皆未识别时退化为 after）。
  const fieldCandidates = useMemo<ExtraCandidate[]>(() => {
    const fields = loginForm?.fields ?? [];
    const account = accountSlotOrder(fields);
    const password = fields.findIndex((f) => f.role === "password");
    const slots = [account, password].filter((i) => i >= 0);
    const first = slots.length > 0 ? Math.min(...slots) : -1;
    const last = slots.length > 0 ? Math.max(...slots) : -1;
    const placementOf = (order: number): ExtraPlacement => {
      if (first < 0) return "after";
      if (order < first) return "before";
      if (order > last) return "after";
      return "between";
    };
    const out: ExtraCandidate[] = [];
    fields.forEach((f, order) => {
      if (f.role !== "unknown") return;
      if (f.type === "hidden" || f.type === "checkbox" || f.type === "radio") return;
      out.push({ ...f, order, placement: placementOf(order) });
    });
    return out;
  }, [loginForm]);

  const setConfigured = useCallback((value: boolean) => {
    setConfiguredState(value);
  }, []);

  return {
    site,
    url: loginUrl,
    configured,
    fieldCandidates,
    setConfigured,
  };
}
