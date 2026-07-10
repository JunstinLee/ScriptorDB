import { useCallback, useRef } from "react";
import { Modal, Input } from "@heroui/react";
import { History, Search, X, Loader2 } from "lucide-react";
import { useHistorySearch } from "../hooks/useHistorySearch";
import type {
  HistorySearchMatch,
  HistorySearchResultItem,
} from "../types";
import { formatRelative, getSessionDisplayName } from "../utils/display";

interface HistorySearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSession: (sessionId: string) => void;
}

function HighlightedText({
  text,
  query,
}: {
  text: string;
  query: string;
}) {
  if (!query.trim()) {
    return <>{text}</>;
  }

  const lowerQuery = query.toLowerCase();
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let keyIndex = 0;

  while (remaining.length > 0) {
    const idx = remaining.toLowerCase().indexOf(lowerQuery);
    if (idx === -1) {
      parts.push(<span key={keyIndex++}>{remaining}</span>);
      break;
    }
    if (idx > 0) {
      parts.push(<span key={keyIndex++}>{remaining.slice(0, idx)}</span>);
    }
    parts.push(
      <mark key={keyIndex++} className="rounded-sm bg-yellow-200 dark:bg-yellow-700">
        {remaining.slice(idx, idx + query.length)}
      </mark>,
    );
    remaining = remaining.slice(idx + query.length);
  }

  return <>{parts}</>;
}

function MatchSnippet({ match }: { match: HistorySearchMatch }) {
  return (
    <p className="line-clamp-1 text-[12px] text-graphite">
      {match.segments.map((seg, i) =>
        seg.highlight ? (
          <mark
            key={i}
            className="rounded-sm bg-yellow-200 dark:bg-yellow-700"
          >
            {seg.text}
          </mark>
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </p>
  );
}

function ResultCard({
  item,
  query,
  onClick,
}: {
  item: HistorySearchResultItem;
  query: string;
  onClick: () => void;
}) {
  const title = getSessionDisplayName(item.title);
  const matches = item.matches.slice(0, 2);

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full flex-col gap-1 rounded-lg border border-grid bg-surface px-3 py-2.5 text-left transition-colors hover:bg-default/40 focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
    >
      <div className="truncate text-[13px] font-medium text-ink">
        <HighlightedText text={title} query={query} />
      </div>
      {matches.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {matches.map((match, i) => (
            <MatchSnippet key={i} match={match} />
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 text-[11px] text-graphite">
        <span>{item.message_count} messages</span>
        <span className="text-grid">·</span>
        <span>Last active {formatRelative(item.last_access)}</span>
      </div>
    </button>
  );
}

export default function HistorySearchModal({
  isOpen,
  onClose,
  onSelectSession,
}: HistorySearchModalProps) {
  const {
    query,
    setQuery,
    results,
    isLoading,
    error,
    hasMore,
    loadMore,
  } = useHistorySearch();

  const scrollRef = useRef<HTMLDivElement | null>(null);

  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const el = e.currentTarget;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      if (nearBottom && hasMore && !isLoading) {
        loadMore();
      }
    },
    [hasMore, isLoading, loadMore],
  );

  const handleSelect = useCallback(
    (sessionId: string) => {
      onSelectSession(sessionId);
      onClose();
    },
    [onSelectSession, onClose],
  );

  const isEmptyQuery = query.trim().length === 0;
  const showEmptyState = !isLoading && results.length === 0;

  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Modal.Container size="lg">
        <Modal.Dialog className="w-[560px] max-w-[calc(100vw-2rem)] max-h-[70vh] flex flex-col overflow-hidden bg-surface">
          <Modal.Header className="border-b border-grid pb-3">
            <div className="flex w-full items-center gap-3">
              <Search className="size-4 shrink-0 text-graphite" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search history..."
                className="flex-1"
                autoFocus
              />
              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1.5 text-graphite transition-colors hover:bg-default/50 hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-cobalt"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
          </Modal.Header>

          <Modal.Body className="min-h-0 flex-1 overflow-hidden p-0">
            <div
              ref={scrollRef}
              onScroll={handleScroll}
              className="flex h-full max-h-[calc(70vh-5rem)] flex-col gap-2 overflow-y-auto px-4 py-3"
            >
              {results.length === 0 && isLoading && (
                <div className="flex items-center justify-center py-8 text-sm text-graphite">
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Loading history…
                </div>
              )}

              {results.length > 0 && (
                <div className="flex flex-col gap-2">
                  {results.map((item) => (
                    <ResultCard
                      key={item.session_id}
                      item={item}
                      query={query}
                      onClick={() => handleSelect(item.session_id)}
                    />
                  ))}
                </div>
              )}

              {showEmptyState && (
                <div className="flex flex-col items-center justify-center gap-2 py-10 text-graphite">
                  <History className="size-8 opacity-40" />
                  <p className="text-sm">
                    {isEmptyQuery
                      ? "No history yet."
                      : "No matching history."}
                  </p>
                </div>
              )}

              {results.length > 0 && isLoading && (
                <div className="flex items-center justify-center py-3 text-xs text-graphite">
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  Loading more…
                </div>
              )}

              {error && !isLoading && (
                <div className="py-2 text-center text-xs text-vermilion">
                  Failed to load more
                </div>
              )}

              {!hasMore && results.length > 0 && !isLoading && (
                <div className="py-2 text-center text-xs text-graphite">
                  End of history
                </div>
              )}
            </div>
          </Modal.Body>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
