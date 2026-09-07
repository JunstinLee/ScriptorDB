import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCredentialStatus } from "../api/loginCredentials";
import type {
  LoginFieldInfo,
  LoginFlowStatus,
  LoginFormPayload,
} from "../types";

/**
 * 登录状态（01/02/03 共享，BrowserWorkspace 挂载处唯一消费点）。
 *
 * 展示由【loginForm 是否出现 + 本地已配置布尔】派生，不依赖会话型
 * login_flow_status SSE（后端事件为旁路/AI 侧，不驱动 UI，避免首次登录
 * 无事件 / 保存后需重登的时序 bug）：
 * - `configured`：进入登录页时查一次 site-status；保存/删除后本地翻转。
 * - `flowStatus`：最近一次 login_flow_status 事件（旁路，仅非敏感状态）。
 */
export interface LoginAutofillState {
  site: string;
  url: string;
  configured: boolean;
  /** 当前登录页的 unknown 可填字段候选（供 01 CredentialSetupPanel 选第三项） */
  fieldCandidates: LoginFieldInfo[];
  /** 最近一次 SSE 旁路状态（可能为 null=尚未收到） */
  flowStatus: LoginFlowStatus | null;
  /** 是否正在做首次 site-status 查询 */
  checking: boolean;
  /** 保存/删除成功后由面板回调调用，本地翻转已配置布尔 */
  setConfigured: (value: boolean) => void;
}

export function useLoginAutofillState(
  loginForm: LoginFormPayload | null,
  flowStatus: LoginFlowStatus | null,
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

  const [configured, setConfiguredState] = useState(false);
  const [checking, setChecking] = useState(false);

  // 进入登录页（loginForm 出现）时查一次 site-status；登录页消失不清 configured
  useEffect(() => {
    if (!site || !loginUrl) {
      return;
    }
    let cancelled = false;
    setChecking(true);
    void fetchCredentialStatus(loginUrl)
      .then((status) => {
        if (!cancelled) setConfiguredState(status.configured);
      })
      .catch(() => {
        // 网络/后端不可用：保持当前值，不打扰（面板由父组件裁决）
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
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
    flowStatus,
    checking,
    setConfigured,
  };
}
