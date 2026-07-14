import { request } from "./core";
import type { HistorySearchResponse } from "../types";

export function searchHistory(
  query: string,
  offset: number = 0,
  limit: number = 10,
): Promise<HistorySearchResponse> {
  const params = new URLSearchParams();
  params.set("q", query);
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  return request<HistorySearchResponse>(`/history/search?${params.toString()}`);
}
