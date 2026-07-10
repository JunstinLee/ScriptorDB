import { useCallback, useEffect, useRef, useState } from "react";
import { searchHistory } from "../api/client";
import type {
  HistorySearchResponse,
  HistorySearchResultItem,
} from "../types";

const LIMIT = 10;
const DEBOUNCE_MS = 300;

export function useHistorySearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HistorySearchResultItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cacheRef = useRef<Map<string, HistorySearchResponse>>(new Map());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestRequestRef = useRef<string>("");

  const cacheKey = useCallback(
    (q: string, pageOffset: number) =>
      `${q.trim().toLowerCase()}|${pageOffset}`,
    [],
  );

  const fetchPage = useCallback(
    async (q: string, pageOffset: number, replace: boolean) => {
      const key = cacheKey(q, pageOffset);

      const cached = cacheRef.current.get(key);
      if (cached) {
        setResults((prev) =>
          replace ? cached.results : [...prev, ...cached.results],
        );
        setTotal(cached.total);
        return;
      }

      const requestId = `${Date.now()}-${Math.random()}`;
      latestRequestRef.current = requestId;
      setIsLoading(true);
      setError(null);

      try {
        const resp = await searchHistory(q, pageOffset, LIMIT);
        if (latestRequestRef.current !== requestId) return;

        cacheRef.current.set(key, resp);
        setResults((prev) =>
          replace ? resp.results : [...prev, ...resp.results],
        );
        setTotal(resp.total);
      } catch (e) {
        if (latestRequestRef.current !== requestId) return;
        setError(e instanceof Error ? e.message : "Failed to load history");
      } finally {
        if (latestRequestRef.current === requestId) {
          setIsLoading(false);
        }
      }
    },
    [cacheKey],
  );

  useEffect(() => {
    setOffset(0);
    setResults([]);
    setTotal(0);
    setError(null);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      void fetchPage(query, 0, true);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, fetchPage]);

  const loadMore = useCallback(() => {
    if (isLoading) return;
    const nextOffset = offset + LIMIT;
    setOffset(nextOffset);
    void fetchPage(query, nextOffset, false);
  }, [isLoading, offset, query, fetchPage]);

  return {
    query,
    setQuery,
    results,
    total,
    isLoading,
    error,
    hasMore: results.length < total,
    loadMore,
  };
}
