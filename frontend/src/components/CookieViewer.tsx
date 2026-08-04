import { useState } from "react";
import { Button, Chip, Modal } from "@heroui/react";
import { Cookie, Trash2, RefreshCw } from "lucide-react";
import type { CookieInfo } from "../types";

interface CookieViewerProps {
  cookies: CookieInfo[];
  loading: boolean;
  currentUrl: string;
  browserLaunched: boolean;
  onDeleteCookie: (name: string) => void;
  onClearAll: () => void;
  onRefresh: () => void;
}

function formatExpires(expires: number | null): string {
  if (expires === null || expires === -1) return "session";
  try {
    return new Date(expires * 1000).toISOString().slice(0, 10);
  } catch {
    return String(expires);
  }
}

function CookieCard({
  cookie,
  onDelete,
}: {
  cookie: CookieInfo;
  onDelete: (name: string) => void;
}) {
  return (
    <div className="rounded-lg border border-grid bg-surface/50 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="truncate text-[13px] font-semibold text-foreground">
            {cookie.name}
          </span>
          <span className="truncate text-[11px] text-graphite">
            domain: {cookie.domain}
          </span>
          <span className="text-[11px] text-muted">
            path: {cookie.path} · expires: {formatExpires(cookie.expires)}
          </span>
          <div className="flex flex-wrap items-center gap-1 mt-0.5">
            {cookie.http_only ? (
              <Chip size="sm" className="bg-blue/10 text-blue text-[10px]">
                httpOnly
              </Chip>
            ) : (
              <Chip size="sm" className="text-[10px] text-muted bg-default/20">
                httpOnly -
              </Chip>
            )}
            {cookie.secure ? (
              <Chip size="sm" className="bg-green/10 text-green text-[10px]">
                secure
              </Chip>
            ) : (
              <Chip size="sm" className="text-[10px] text-muted bg-default/20">
                secure -
              </Chip>
            )}
            <Chip size="sm" className="text-[10px] text-graphite bg-default/20">
              {cookie.same_site}
            </Chip>
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onPress={() => onDelete(cookie.name)}
          className="h-7 shrink-0 text-[11px]"
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

export default function CookieViewer({
  cookies,
  loading,
  currentUrl,
  browserLaunched,
  onDeleteCookie,
  onClearAll,
  onRefresh,
}: CookieViewerProps) {
  const [clearOpen, setClearOpen] = useState(false);

  if (!browserLaunched) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3 px-2">
      <div className="border-t border-grid" />

      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
        Cookies
      </p>

      {currentUrl && (
        <p className="truncate text-xs text-graphite flex items-center gap-1">
          <Cookie className="size-3 shrink-0" />
          {currentUrl}
        </p>
      )}

      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="secondary"
          onPress={onRefresh}
          isDisabled={loading}
          className="h-7 text-[11px]"
        >
          <RefreshCw className="mr-1 size-3" />
          Refresh
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onPress={() => setClearOpen(true)}
          className="h-7 text-[11px]"
        >
          <Trash2 className="mr-1 size-3" />
          Clear All
        </Button>
        <span className="ml-auto text-[11px] text-muted">
          {cookies.length} total
        </span>
      </div>

      {loading ? (
        <p className="text-xs text-muted py-2">Loading cookies...</p>
      ) : cookies.length === 0 ? (
        <p className="text-xs text-muted py-2">No cookies for this page.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {cookies.map((c) => (
            <CookieCard key={`${c.name}@${c.domain}`} cookie={c} onDelete={onDeleteCookie} />
          ))}
        </div>
      )}

      <Modal.Backdrop isOpen={clearOpen} onOpenChange={(open) => { if (!open) setClearOpen(false); }}>
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-[360px] bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>Clear All Cookies</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm text-graphite leading-relaxed">
                This will delete all {cookies.length} cookies from the current browser session.
                This action cannot be undone.
              </p>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onPress={() => setClearOpen(false)}>
                Cancel
              </Button>
              <Button
                onPress={() => {
                  onClearAll();
                  setClearOpen(false);
                }}
              >
                Clear All
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </div>
  );
}
