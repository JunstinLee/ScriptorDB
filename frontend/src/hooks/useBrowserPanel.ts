import { useCallback, useEffect, useState } from "react";
import {
  useBrowser,
  useBrowserActions,
  useProfiles,
  useCookies,
} from "./useBrowser";
import { fetchSettings } from "../api/settings";
import {
  saveProfile,
  loadProfile,
  deleteProfile,
  updateProfile,
  deleteCookie,
  clearAllCookies,
} from "../api/browser";

/**
 * 浏览器面板状态与操作编排。
 *
 * 收编原来散落在 App 组合根里的浏览器相关状态：
 * - 浏览器轮询（useBrowser）、动作、Profiles、Cookies 四个 hook
 * - Profile/Cookie 的保存/加载/删除回调（调 API + 刷新列表的透传）
 * - browser_enabled 配置拉取与刷新（设置弹窗关闭后经 refreshBrowserEnabled 触发）
 */
export function useBrowserPanel(workspaceId: string | null | undefined) {
  const [browserActive, setBrowserActive] = useState(false);
  const [activeMainTab, setActiveMainTab] = useState<"chat" | "browser">("chat");
  const [browserEnabled, setBrowserEnabled] = useState(false);
  const [settingsVersion, setSettingsVersion] = useState(0);

  const {
    state: browserState,
    loading: browserLoading,
    error: browserError,
    refresh: refreshBrowser,
  } = useBrowser(browserEnabled, workspaceId ?? null);
  const { actions: browserActions, appendAction, clearActions } = useBrowserActions();
  const { profiles, loading: profilesLoading, refresh: refreshProfiles } = useProfiles(workspaceId ?? null);
  const { cookies, loading: cookiesLoading, refresh: refreshCookies } = useCookies(
    workspaceId ?? null,
    browserState?.launched ?? false,
  );

  useEffect(() => {
    if (!workspaceId) return;
    fetchSettings()
      .then((s) => setBrowserEnabled(s.browser_enabled))
      .catch((e) => {
        console.error("fetchSettings failed:", e);
      });
  }, [settingsVersion, workspaceId]);

  const onBrowserActivity = useCallback(() => {
    setBrowserActive(true);
    setBrowserEnabled(true);
  }, []);

  const handleSaveProfile = useCallback(async (name: string) => {
    await saveProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleLoadProfile = useCallback(async (name: string) => {
    await loadProfile(name);
    refreshCookies();
  }, [refreshCookies]);

  const handleDeleteProfile = useCallback(async (name: string) => {
    await deleteProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleUpdateProfile = useCallback(async (name: string) => {
    await updateProfile(name);
    refreshProfiles();
  }, [refreshProfiles]);

  const handleDeleteCookie = useCallback(async (name: string) => {
    await deleteCookie(name);
    refreshCookies();
  }, [refreshCookies]);

  const handleClearCookies = useCallback(async () => {
    await clearAllCookies();
    refreshCookies();
  }, [refreshCookies]);

  /** 设置弹窗关闭后调用：重新拉取 browser_enabled 配置 */
  const refreshBrowserEnabled = useCallback(() => {
    setSettingsVersion((v) => v + 1);
  }, []);

  return {
    browserActive,
    setBrowserActive,
    activeMainTab,
    setActiveMainTab,
    browserEnabled,
    browserState,
    browserLoading,
    browserError,
    refreshBrowser,
    browserActions,
    appendAction,
    clearActions,
    profiles,
    profilesLoading,
    cookies,
    cookiesLoading,
    refreshCookies,
    handleSaveProfile,
    handleLoadProfile,
    handleDeleteProfile,
    handleUpdateProfile,
    handleDeleteCookie,
    handleClearCookies,
    onBrowserActivity,
    refreshBrowserEnabled,
  };
}
