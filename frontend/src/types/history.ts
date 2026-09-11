export interface HistoryMatchSegment {
  text: string;
  highlight: boolean;
}

export interface HistorySearchMatch {
  segments: HistoryMatchSegment[];
}

export interface HistorySearchResultItem {
  session_id: string;
  title: string | null;
  created_at: string;
  last_access: string;
  message_count: number;
  match_count: number;
  matches: HistorySearchMatch[];
}

export interface HistorySearchResponse {
  results: HistorySearchResultItem[];
  total: number;
  offset: number;
  limit: number;
}
