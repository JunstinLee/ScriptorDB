import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCredentialStatus } from "../api/loginCredentials";
import type {
  LoginFieldInfo,
  LoginFormPayload,
} from "../types";

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
  /** 当前登录页的 unknown 可填字段候选（供 01 CredentialSetupPanel 选第三项） */
  fieldCandidates: LoginFieldInfo[];
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

  const fieldCandidates = useMemo<LoginFieldInfo[]>(
    () =>
      (loginForm?.fields ?? []).filter(
        (f) =>
          f.role === "unknown" &&
          f.type !== "hidden" &&
          f.type !== "checkbox" &&
          f.type !== "radio",
      ),
    [loginForm],
  );

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
