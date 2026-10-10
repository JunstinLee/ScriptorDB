import { useCallback, useEffect, useState } from "react";
import { Button, Input, Label, Modal } from "@heroui/react";
import { Eye, EyeOff, KeyRound, RefreshCw } from "lucide-react";
import { fetchSettings, saveApiKey, testApiKey } from "../api/client";
import { t } from "../i18n";
import type { ApiKeyStatusKind, ProviderInfo } from "../types";
import AlertBanner from "./common/AlertBanner";
import ProviderSelect from "./common/ProviderSelect";

interface ApiKeyRequiredModalProps {
  isOpen: boolean;
  status: ApiKeyStatusKind | null;
  provider: string | null;
  error: string | null;
  onResolved: () => void;
}

type FormStatus =
  | { kind: "idle" }
  | { kind: "busy" }
  | { kind: "error"; message: string }
  | { kind: "success"; message: string };

/**
 * 主动检测到 API Key 缺失/无效时弹出的弹窗。
 *
 * 保存成功后给出明确提示，由用户自己关闭——不拿“自动关闭”当成功反馈。
 * 关闭后不会因为父层的状态条件仍为真而自动弹回，只在 isOpen 的下一个上升沿重新打开。
 */
export default function ApiKeyRequiredModal({
  isOpen,
  status,
  provider,
  error,
  onResolved,
}: ApiKeyRequiredModalProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [configuredSet, setConfiguredSet] = useState<Set<string>>(new Set());
  const [selectedProvider, setSelectedProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [formStatus, setFormStatus] = useState<FormStatus>({ kind: "idle" });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isOpen) setVisible(true);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    setApiKey("");
    setShowKey(false);
    setFormStatus({ kind: "idle" });
    void fetchSettings()
      .then((s) => {
        if (!active) return;
        setProviders(s.providers);
        setConfiguredSet(new Set(s.providers_with_keys));
        setSelectedProvider(provider || s.llm_provider);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [isOpen, provider]);

  const handleSave = useCallback(async () => {
    if (!apiKey.trim()) {
      setFormStatus({ kind: "error", message: t("settings.api_keys.empty") });
      return;
    }
    setFormStatus({ kind: "busy" });
    try {
      const resp = await saveApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (!resp.ok) {
        setFormStatus({ kind: "error", message: resp.error || t("settings.api_keys.save_failed") });
        return;
      }
      setApiKey("");
      setFormStatus({
        kind: "success",
        message: t("settings.api_keys.saved_for", { provider: selectedProvider }),
      });
      onResolved();
    } catch (e) {
      setFormStatus({
        kind: "error",
        message: e instanceof Error ? e.message : t("settings.api_keys.save_failed"),
      });
    }
  }, [apiKey, onResolved, selectedProvider]);

  const handleTest = useCallback(async () => {
    if (!apiKey.trim()) {
      setFormStatus({ kind: "error", message: t("settings.api_keys.enter_to_test") });
      return;
    }
    setFormStatus({ kind: "busy" });
    try {
      const resp = await testApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (resp.ok) {
        setFormStatus({ kind: "success", message: t("settings.api_keys.valid") });
      } else {
        setFormStatus({
          kind: "error",
          message: resp.error || t("settings.api_keys.test_failed"),
        });
      }
    } catch (e) {
      setFormStatus({
        kind: "error",
        message: e instanceof Error ? e.message : t("settings.api_keys.test_failed"),
      });
    }
  }, [apiKey, selectedProvider]);

  const heading =
    status === "invalid"
      ? t("settings.api_keys.state_invalid_title")
      : status === "unknown"
        ? t("settings.api_keys.state_unknown_title")
        : status === "valid"
          ? t("settings.api_keys.state_valid_title")
          : t("settings.api_keys.state_required_title");

  return (
    <Modal.Backdrop
      isOpen={visible}
      onOpenChange={(open) => {
        if (!open) setVisible(false);
      }}
    >
      <Modal.Container size="lg" scroll="inside">
        <Modal.Dialog className="sm:max-w-120 bg-surface">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Icon className="bg-accent-soft text-accent-soft-foreground">
              <KeyRound className="size-5" />
            </Modal.Icon>
            <Modal.Heading>{heading}</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            <p className="text-sm text-muted -mt-2">
              {status === "unknown"
                ? t("settings.api_keys.state_unknown_desc", {
                    provider: provider ?? t("settings.api_keys.provider_fallback"),
                  })
                : status === "invalid"
                  ? t("settings.api_keys.state_invalid_desc", {
                      provider:
                        provider ?? t("settings.api_keys.provider_fallback_sentence"),
                    })
                  : status === "valid"
                    ? t("settings.api_keys.state_valid_desc", {
                        provider:
                          provider ?? t("settings.api_keys.provider_fallback_sentence"),
                      })
                    : t("settings.api_keys.state_required_desc", {
                        provider:
                          provider ?? t("settings.api_keys.provider_fallback_current"),
                      })}
            </p>

            {status === "unknown" && error && (
              <AlertBanner variant="error" message={error} />
            )}

            <ProviderSelect
              providers={providers}
              value={selectedProvider}
              onChange={(v) => {
                setSelectedProvider(v);
                setFormStatus({ kind: "idle" });
              }}
              configuredSet={configuredSet}
              name="api-key-modal-provider"
            />

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="api-key-modal-input" className="text-xs text-graphite">
                {t("settings.api_keys.label")}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="api-key-modal-input"
                  name="api_key"
                  className="flex-1"
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setFormStatus({ kind: "idle" });
                  }}
                  placeholder="sk-…"
                  autoComplete="off"
                />
                <Button
                  variant="ghost"
                  isIconOnly
                  aria-label={showKey ? t("settings.api_keys.hide") : t("settings.api_keys.show")}
                  onPress={() => setShowKey((v) => !v)}
                >
                  {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </div>

            {formStatus.kind === "error" && (
              <AlertBanner variant="error" message={formStatus.message} />
            )}
            {formStatus.kind === "success" && (
              <AlertBanner variant="success" message={formStatus.message} />
            )}

            <div className="flex flex-wrap justify-end gap-2">
              {status === "unknown" && (
                <Button variant="tertiary" onPress={onResolved}>
                  <RefreshCw className="size-4" />
                  {t("settings.api_keys.retry_check")}
                </Button>
              )}
              <Button
                variant="secondary"
                onPress={() => void handleTest()}
                isDisabled={formStatus.kind === "busy" || !apiKey.trim()}
              >
                {t("settings.api_keys.test")}
              </Button>
              <Button
                variant="primary"
                onPress={() => void handleSave()}
                isDisabled={formStatus.kind === "busy" || !apiKey.trim()}
              >
                {formStatus.kind === "busy" ? t("settings.api_keys.saving") : t("settings.api_keys.save_key")}
              </Button>
            </div>
          </Modal.Body>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
