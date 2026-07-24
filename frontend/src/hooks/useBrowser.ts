import { useState, useEffect, useCallback, useRef } from "react";
import { fetchBrowserState } from "../api/browser";
import type { BrowserState } from "../types";

/** 轮询间隔（毫秒） */
const POLL_INTERVAL_MS = 2000;

interface UseBrowserReturn {
  state: BrowserState | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * 浏览器状态轮询 Hook。
 * 仅当 `browserEnabled` 为 true 时开启轮询。
 * `workspaceId` 变化时重置状态。
 */
export function useBrowser(
  browserEnabled: boolean,
  workspaceId: string | null
): UseBrowserReturn {
  const [state, setState] = useState<BrowserState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchState = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      const data = await fetchBrowserState();
      if (isMountedRef.current) {
        setState(data);
        setError(null);
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : "获取浏览器状态失败");
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    // 重置状态
    setState(null);
    setLoading(false);
    setError(null);

    // 清理已有轮询
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    if (!workspaceId || !browserEnabled) {
      return () => {
        isMountedRef.current = false;
      };
    }

    // 首次获取
    setLoading(true);
    void fetchState();

    // 开启轮询
    pollRef.current = setInterval(() => {
      void fetchState();
    }, POLL_INTERVAL_MS);

    return () => {
      isMountedRef.current = false;
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [browserEnabled, workspaceId, fetchState]);

  const refresh = useCallback(() => {
    setLoading(true);
    void fetchState();
  }, [fetchState]);

  return { state, loading, error, refresh };
}
