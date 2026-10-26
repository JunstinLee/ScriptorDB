import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal } from "@heroui/react";
import { Globe, Save, Upload } from "lucide-react";
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

function monogram(domain: string): string {
  const host = normalizeHost(domain);
  return (host || domain).charAt(0).toUpperCase();
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toISOString().slice(0, 10);
  } catch {
    return iso.slice(0, 10);
  }
}

function ProfileRow({
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
      <div className="flex flex-col gap-1.5 py-2">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent/10 font-mono text-[11px] font-bold text-accent">
            {monogram(profile.domain)}
          </span>
          <span className="truncate text-[13px] font-semibold text-foreground">
            {profile.name}
          </span>
        </div>
        <p className="truncate text-[11px] text-muted">
          <span className="font-mono">{profile.domain}</span>
          <span>
            {" · "}
            {t("browser.profile_card_meta", {
              count: profile.cookie_count,
              date: formatDate(profile.updated_at),
            })}
          </span>
        </p>
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            onPress={() => setLoadOpen(true)}
            className="h-7 text-[11px]"
          >
            <Upload className="mr-1 size-3" />
            {t("browser.apply_profile")}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onPress={() => onUpdate(profile.name)}
            className="h-7 text-[11px]"
          >
            {t("browser.overwrite_profile")}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onPress={() => setDeleteOpen(true)}
            className="h-7 text-[11px]"
          >
            {t("common.delete")}
          </Button>
        </div>
      </div>

      <Modal.Backdrop isOpen={loadOpen} onOpenChange={(open) => { if (!open) setLoadOpen(false); }}>
        <Modal.Container size="sm">
          <Modal.Dialog className="sm:max-w-90 bg-surface">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{t("browser.apply_profile_title")}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-[13px] text-muted leading-relaxed">
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
                {t("browser.apply_profile")}
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
              <p className="text-[13px] text-muted leading-relaxed">
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
                {t("common.delete")}
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
    <div className="flex flex-col gap-3">
      <p className="text-[11px] font-semibold text-muted">
        {t("browser.profiles_title")}
      </p>

      {!browserLaunched ? (
        <div className="flex flex-col gap-1">
          <p className="text-[13px] text-foreground">
            {t("browser.profiles_launch_first")}
          </p>
          <p className="text-[11px] text-muted">
            {t("browser.profiles_launch_hint")}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
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
          <div className="rounded-md border border-warning/30 bg-warning/5 px-2 py-1.5 text-[11px] text-warning">
            <Globe className="mr-1 inline size-3" />
            {t("browser.load_profile_warning")}
          </div>
        </div>
      )}

      <div className="border-t border-default" />

      {loading ? (
        <p className="py-2 text-[11px] text-muted">{t("browser.profiles_loading")}</p>
      ) : profiles.length === 0 ? (
        <div className="flex flex-col gap-1 py-2">
          <p className="text-[13px] text-foreground">{t("browser.profiles_empty")}</p>
          <p className="text-[11px] text-muted">
            {t("browser.profiles_empty_hint")}
          </p>
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-default">
          {profiles.map((p) => (
            <ProfileRow
              key={p.name}
              profile={p}
              onLoad={onLoad}
              onDelete={onDelete}
              onUpdate={onUpdate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
