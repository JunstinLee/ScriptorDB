import { useState, useMemo } from "react";
import { Button, ListBox, Modal, Popover, Select } from "@heroui/react";
import { ShieldCheck, ShieldOff, Upload, Cookie, HardDrive, Globe, Activity } from "lucide-react";
import type { BrowserProfileItem, CookieInfo, BrowserActionEvent } from "../types";
import { AgentActivityTimeline } from "./AgentActivityTimeline";

interface BrowserSessionInfoProps {
  profiles: BrowserProfileItem[];
  cookies: CookieInfo[];
  cookiesLoading: boolean;
  browserLaunched: boolean;
  currentUrl: string;
  onLoadProfile?: (name: string) => void;
  actions?: BrowserActionEvent[];
  isRunning?: boolean;
}

const AUTH_COOKIE_PATTERNS = [
  /^user_session$/i,
  /^_session$/i,
  /^session$/i,
  /^sid$/i,
  /^token$/i,
  /^auth/i,
  /^JSESSIONID$/i,
  /^connect\.sid$/i,
  /^_gh_sess$/i,
  /^user_logged_in$/i,
  /^remember_user_token$/i,
];

function hasAuthCookie(cookies: CookieInfo[]): boolean {
  return cookies.some((c) =>
    AUTH_COOKIE_PATTERNS.some((pattern) => pattern.test(c.name)),
  );
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function estimateStorageSize(cookies: CookieInfo[]): string {
  const totalBytes = cookies.reduce((sum, c) => {
    return sum + c.name.length + c.domain.length + c.path.length + 64;
  }, 0);
  if (totalBytes < 1024) return `~${totalBytes}B`;
  if (totalBytes < 1024 * 1024) return `~${Math.round(totalBytes / 1024)}KB`;
  return `~${Math.round(totalBytes / (1024 * 1024))}MB`;
}

export function BrowserSessionInfo({
  profiles,
  cookies,
  cookiesLoading,
  browserLaunched,
  currentUrl,
  onLoadProfile,
  actions,
  isRunning,
}: BrowserSessionInfoProps) {
  const [loadOpen, setLoadOpen] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<string>("");

  const isLoggedIn = useMemo(() => hasAuthCookie(cookies), [cookies]);
  const currentDomain = useMemo(() => extractDomain(currentUrl), [currentUrl]);
  const storageSize = useMemo(() => estimateStorageSize(cookies), [cookies]);

  const domainMatchedProfiles = useMemo(
    () => profiles.filter((p) => currentDomain && currentDomain.includes(p.domain)),
    [profiles, currentDomain],
  );

  const handleLoad = () => {
    if (!selectedProfile || !onLoadProfile) return;
    onLoadProfile(selectedProfile);
    setLoadOpen(false);
    setSelectedProfile("");
  };

  if (!browserLaunched) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 border-b border-grid px-3 py-1.5">
      <div className="flex items-center gap-1.5 shrink-0">
        {isLoggedIn ? (
          <ShieldCheck className="size-3.5 text-green-400" />
        ) : (
          <ShieldOff className="size-3.5 text-muted" />
        )}
        <span className="text-[11px] font-medium">
          {isLoggedIn ? (
            <span className="text-green-400">Logged in</span>
          ) : (
            <span className="text-muted">Not logged in</span>
          )}
        </span>
        {isLoggedIn && cookies.length > 0 && (
          <span className="text-[10px] text-muted/70 truncate max-w-[120px]">
            ({cookies.find(c => AUTH_COOKIE_PATTERNS.some(p => p.test(c.name)))?.name ?? ""})
          </span>
        )}
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        <Cookie className="size-3 text-muted" />
        <span className="text-[11px] text-graphite">
          {cookiesLoading ? "..." : `${cookies.length} cookies`}
        </span>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        <HardDrive className="size-3 text-muted" />
        <span className="text-[11px] text-graphite">{storageSize}</span>
      </div>

      {actions && actions.length > 0 && (
        <div className="flex items-center gap-1.5 shrink-0">
          <Popover>
            <Popover.Trigger>
              <button
                type="button"
                className="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-graphite transition-colors hover:bg-surface hover:text-foreground"
              >
                <Activity className="size-3" />
                <span>Actions ({actions.length})</span>
              </button>
            </Popover.Trigger>
            <Popover.Content placement="bottom" className="p-0">
              <Popover.Dialog className="p-0">
                <AgentActivityTimeline
                  events={actions}
                  isRunning={isRunning ?? false}
                />
              </Popover.Dialog>
            </Popover.Content>
          </Popover>
        </div>
      )}

      <div className="flex items-center gap-1.5 ml-auto">
        <span className="text-[10px] text-muted">
          {profiles.length > 0 ? `Profile: ${profiles.length} saved` : "Profile: none saved"}
        </span>
        {profiles.length > 0 && (
          <Button
            size="sm"
            variant="secondary"
            onPress={() => setLoadOpen(true)}
            className="h-6 text-[11px]"
          >
            <Upload className="mr-1 size-3" />
            Load Profile
          </Button>
        )}
      </div>

      <Modal.Backdrop
        isOpen={loadOpen}
        onOpenChange={(open) => {
          if (!open) setLoadOpen(false);
        }}
      >
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-[360px] bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>Load Profile</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-xs text-graphite mb-3">
                Select a saved profile to restore its browser cookies and login state.
              </p>
              <Select
                selectedKey={selectedProfile}
                onSelectionChange={(key) => setSelectedProfile(String(key))}
                placeholder="Select a profile..."
              >
                <Select.Trigger>
                  <Select.Value />
                  <Select.Indicator />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {domainMatchedProfiles.length > 0 &&
                      domainMatchedProfiles.map((p) => (
                        <ListBox.Item key={p.name} id={p.name} textValue={p.name}>
                          <div className="flex items-center gap-2">
                            <Globe className="size-3 shrink-0 text-cobalt" />
                            <div className="flex flex-col">
                              <span className="text-[13px] font-semibold">{p.name}</span>
                              <span className="text-[10px] text-muted">{p.domain} · {p.cookie_count} cookies</span>
                            </div>
                          </div>
                        </ListBox.Item>
                      ))}
                    {profiles.filter((p) => !domainMatchedProfiles.includes(p)).map((p) => (
                      <ListBox.Item key={p.name} id={p.name} textValue={p.name}>
                        <div className="flex items-center gap-2">
                          <Globe className="size-3 shrink-0 text-muted" />
                          <div className="flex flex-col">
                            <span className="text-[13px]">{p.name}</span>
                            <span className="text-[10px] text-muted">{p.domain} · {p.cookie_count} cookies</span>
                          </div>
                        </div>
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onPress={() => setLoadOpen(false)}>
                Cancel
              </Button>
              <Button
                onPress={handleLoad}
                isDisabled={!selectedProfile}
              >
                Load
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </div>
  );
}
