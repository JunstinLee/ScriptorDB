import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal } from "@heroui/react";
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

function formatExpires(expires: number | null, sessionLabel: string): string {
  if (expires === null || expires === -1) return sessionLabel;
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
  const { t } = useTranslation();

  const flags = [
    cookie.http_only ? "httponly" : null,
    cookie.secure ? "secure" : null,
    cookie.same_site ? `samesite=${cookie.same_site.toLowerCase()}` : null,
  ].filter(Boolean) as string[];

  return (
    <div className="flex items-start gap-2 px-3 py-2">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[13px] font-semibold text-foreground">
          {cookie.name}
        </span>
        <span className="truncate text-[11px] text-muted">
          <span className="font-mono">{cookie.domain}</span>
          <span>
            {" · "}
            {cookie.path}
            {" · "}
            {formatExpires(cookie.expires, t("browser.cookie_session"))}
            {flags.length > 0 && ` · ${flags.join(" · ")}`}
          </span>
        </span>
      </div>
      <button
        type="button"
        onClick={() => onDelete(cookie.name)}
        aria-label={t("browser.delete_cookie", { name: cookie.name })}
        className="shrink-0 rounded p-1 text-muted transition-colors hover:bg-default/40 hover:text-danger"
      >
        <Trash2 className="size-3" />
      </button>
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
  const { t } = useTranslation();
  const [clearOpen, setClearOpen] = useState(false);

  if (!browserLaunched) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="border-t border-default" />

      <p className="text-[11px] font-semibold text-muted">
        {t("browser.cookies_title")}
      </p>

      {currentUrl && (
        <p className="truncate text-[11px] text-muted flex items-center gap-1">
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
          {t("browser.refresh_cookies")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onPress={() => setClearOpen(true)}
          className="h-7 text-[11px]"
        >
          <Trash2 className="mr-1 size-3" />
          {t("browser.clear_all")}
        </Button>
        <span className="ml-auto text-[11px] text-muted">
          {t("browser.cookies_total", { count: cookies.length })}
        </span>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2 px-3 py-1" aria-hidden>
          {[0, 1].map((i) => (
            <div key={i} className="h-3 w-2/3 rounded bg-default/40" />
          ))}
        </div>
      ) : cookies.length === 0 ? (
        <div className="flex flex-col gap-1 px-3 py-2">
          <p className="text-[13px] text-foreground">
            {t("browser.cookies_empty")}
          </p>
          <p className="text-[11px] text-muted">
            {t("browser.cookies_empty_hint")}
          </p>
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-default">
          {cookies.map((c) => (
            <CookieCard key={`${c.name}@${c.domain}`} cookie={c} onDelete={onDeleteCookie} />
          ))}
        </div>
      )}

      <Modal.Backdrop isOpen={clearOpen} onOpenChange={(open) => { if (!open) setClearOpen(false); }}>
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-90 bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{t("browser.clear_all_title")}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-[13px] text-muted leading-relaxed">
                {t("browser.clear_all_confirm", { count: cookies.length })}
              </p>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onPress={() => setClearOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button
                onPress={() => {
                  onClearAll();
                  setClearOpen(false);
                }}
              >
                {t("browser.clear_all")}
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </div>
  );
}
