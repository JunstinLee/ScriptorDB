import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, Modal } from "@heroui/react";
import { Globe, Save, Trash2, Upload, RefreshCw } from "lucide-react";
import type { BrowserProfileItem } from "../types";

interface BrowserProfilePanelProps {
  profiles: BrowserProfileItem[];
  loading: boolean;
  onSave: (name: string) => void;
  onLoad: (name: string) => void;
  onDelete: (name: string) => void;
  onUpdate: (name: string) => void;
  browserLaunched: boolean;
}

function normalizeHost(domain: string): string {
  let host = domain.trim().toLowerCase();
  host = host.replace(/^[a-z][a-z0-9+.-]*:\/\//, "");
  host = host.split(/[/?#]/)[0].split(":")[0];
  return host.replace(/^www\./, "");
}

function isHost(host: string, suffix: string): boolean {
  return host === suffix || host.endsWith("." + suffix);
}

function domainIcon(domain: string) {
  const host = normalizeHost(domain);
  if (isHost(host, "github.com")) return "gh";
  if (isHost(host, "gitlab.com")) return "gl";
  if (isHost(host, "amazon.com") || isHost(host, "amazonaws.com")) return "aws";
  if (isHost(host, "google.com")) return "G";
  if (isHost(host, "stackoverflow.com")) return "SO";
  return (host || domain).charAt(0).toUpperCase();
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toISOString().slice(0, 10);
  } catch {
    return iso.slice(0, 10);
  }
}

function ProfileCard({
  profile,
  onLoad,
  onDelete,
  onUpdate,
}: {
  profile: BrowserProfileItem;
  onLoad: (name: string) => void;
  onDelete: (name: string) => void;
  onUpdate: (name: string) => void;
}) {
  const { t } = useTranslation();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [loadOpen, setLoadOpen] = useState(false);

  return (
    <>
      <Card className="rounded-lg border border-grid bg-surface/50">
        <Card.Content className="flex flex-col gap-2 p-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-cobalt/10 text-[11px] font-bold text-cobalt">
              {domainIcon(profile.domain)}
            </span>
            <span className="truncate text-[13px] font-semibold text-foreground">
              {profile.name}
            </span>
          </div>
          <p className="truncate text-[11px] text-graphite">
            {profile.domain}
          </p>
          <p className="text-[11px] text-muted">
            {t("browser.profile_card_meta", {
              count: profile.cookie_count,
              date: formatDate(profile.updated_at),
            })}
          </p>
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              variant="secondary"
              onPress={() => setLoadOpen(true)}
              className="h-7 text-[11px]"
            >
              <Upload className="mr-1 size-3" />
              {t("browser.load")}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onPress={() => onUpdate(profile.name)}
              className="h-7 text-[11px]"
            >
              <RefreshCw className="mr-1 size-3" />
              {t("browser.update")}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onPress={() => setDeleteOpen(true)}
              className="h-7 text-[11px]"
            >
              <Trash2 className="mr-1 size-3" />
              {t("browser.delete")}
            </Button>
          </div>
        </Card.Content>
      </Card>

      <Modal.Backdrop isOpen={loadOpen} onOpenChange={(open) => { if (!open) setLoadOpen(false); }}>
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-90 bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{t("browser.load_profile_title")}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm text-graphite leading-relaxed">
                {t("browser.load_profile_confirm")}
              </p>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onPress={() => setLoadOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button
                onPress={() => {
                  onLoad(profile.name);
                  setLoadOpen(false);
                }}
              >
                {t("browser.load")}
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>

      <Modal.Backdrop isOpen={deleteOpen} onOpenChange={(open) => { if (!open) setDeleteOpen(false); }}>
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-90 bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{t("browser.delete_profile_title")}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm text-graphite leading-relaxed">
                {t("browser.delete_profile_confirm", { name: profile.name })}
              </p>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onPress={() => setDeleteOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button
                onPress={() => {
                  onDelete(profile.name);
                  setDeleteOpen(false);
                }}
              >
                {t("browser.delete")}
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </>
  );
}

export default function BrowserProfilePanel({
  profiles,
  loading,
  onSave,
  onLoad,
  onDelete,
  onUpdate,
  browserLaunched,
}: BrowserProfilePanelProps) {
  const { t } = useTranslation();
  const [saveName, setSaveName] = useState("");

  const handleSave = () => {
    const trimmed = saveName.trim();
    if (!trimmed) return;
    onSave(trimmed);
    setSaveName("");
  };

  return (
    <div className="flex flex-col gap-3 px-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
        {t("browser.profiles_title")}
      </p>

      {!browserLaunched ? (
        <p className="text-xs text-muted italic">
          {t("browser.profiles_launch_first")}
        </p>
      ) : (
        <div className="flex gap-1.5">
          <Input
            placeholder={t("browser.profile_save_placeholder")}
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
            className="flex-1"
          />
          <Button
            size="sm"
            onPress={handleSave}
            isDisabled={!saveName.trim()}
            className="h-9 shrink-0"
          >
            <Save className="mr-1 size-3" />
            {t("common.save")}
          </Button>
        </div>
      )}

      <div className="border-t border-grid" />

      {loading ? (
        <p className="text-xs text-muted py-2">{t("browser.profiles_loading")}</p>
      ) : profiles.length === 0 ? (
        <p className="text-xs text-muted py-2">{t("browser.profiles_empty")}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {profiles.map((p) => (
            <ProfileCard
              key={p.name}
              profile={p}
              onLoad={onLoad}
              onDelete={onDelete}
              onUpdate={onUpdate}
            />
          ))}
        </div>
      )}

      <div className="rounded-md border border-amber/30 bg-amber/5 px-3 py-2 text-[11px] text-amber">
        <Globe className="mr-1 inline size-3" />
        {t("browser.load_profile_warning")}
      </div>
    </div>
  );
}
