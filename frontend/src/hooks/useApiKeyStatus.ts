import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApiKeyStatus } from "../api/client";
import type { ApiKeyStatusKind } from "../types";

export interface UseApiKeyStatusResult {
  /** null until the first check completes, or when there is no workspace. */
  kind: ApiKeyStatusKind | null;
  provider: string | null;
  error: string | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

/**
 * 主动询问后端“当前 provider 的 API Key 是否可用”。
 *
 * 挂载时会检测一次，工作区切换时重新检测；失败时保留上一次结果——
 * 网络抖动不应该让弹窗突然冒出来。
 */
export function useApiKeyStatus(
  workspaceId: string | null | undefined,
): UseApiKeyStatusResult {
  const [kind, setKind] = useState<ApiKeyStatusKind | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const requestIdRef = useRef(0);

  const load = useCallback(
    async (force: boolean) => {
      if (!workspaceId) {
        setKind(null);
        setProvider(null);
        setError(null);
        return;
      }
      const requestId = ++requestIdRef.current;
      setIsLoading(true);
      try {
        const result = await fetchApiKeyStatus(undefined, force);
        if (requestId !== requestIdRef.current) return;
        setKind(result.status);
        setProvider(result.provider);
        setError(result.error);
      } catch {
        // 保留上一次结果
      } finally {
        if (requestId === requestIdRef.current) setIsLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  const refresh = useCallback(async () => {
    await load(true);
  }, [load]);

  return { kind, provider, error, isLoading, refresh };
}
