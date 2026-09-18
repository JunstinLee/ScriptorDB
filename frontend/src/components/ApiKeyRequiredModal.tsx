import { useCallback, useEffect, useState } from "react";
import { Button, Input, Label, Modal } from "@heroui/react";
import { Eye, EyeOff, KeyRound, RefreshCw } from "lucide-react";
import { fetchSettings, saveApiKey, testApiKey } from "../api/client";
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
      setFormStatus({ kind: "error", message: "API key cannot be empty" });
      return;
    }
    setFormStatus({ kind: "busy" });
    try {
      const resp = await saveApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (!resp.ok) {
        setFormStatus({ kind: "error", message: resp.error || "Save failed" });
        return;
      }
      setApiKey("");
      setFormStatus({
        kind: "success",
        message: `API key saved for ${selectedProvider}.`,
      });
      onResolved();
    } catch (e) {
      setFormStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Save failed",
      });
    }
  }, [apiKey, onResolved, selectedProvider]);

  const handleTest = useCallback(async () => {
    if (!apiKey.trim()) {
      setFormStatus({ kind: "error", message: "Enter an API key to test" });
      return;
    }
    setFormStatus({ kind: "busy" });
    try {
      const resp = await testApiKey({
        provider: selectedProvider,
        api_key: apiKey.trim(),
      });
      if (resp.ok) {
        setFormStatus({ kind: "success", message: "API key is valid" });
      } else {
        setFormStatus({
          kind: "error",
          message: resp.error || "Test failed",
        });
      }
    } catch (e) {
      setFormStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Test failed",
      });
    }
  }, [apiKey, selectedProvider]);

  const heading =
    status === "invalid"
      ? "Invalid API key"
      : status === "unknown"
        ? "Could not verify API key"
        : status === "valid"
          ? "API key configured"
          : "API key required";

  return (
    <Modal.Backdrop
      isOpen={visible}
      onOpenChange={(open) => {
        if (!open) setVisible(false);
      }}
    >
      <Modal.Container size="lg" scroll="inside">
        <Modal.Dialog className="sm:max-w-[480px] bg-surface">
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
                ? `Could not reach ${provider ?? "the provider"} to check the API key. Check your connection and retry.`
                : status === "invalid"
                  ? `${provider ?? "The provider"} rejected the stored API key. Enter a new one to continue.`
                  : status === "valid"
                    ? `${provider ?? "The provider"} is ready to use. Close this window to continue.`
                    : `No API key is set for ${provider ?? "the current provider"}. Enter one to continue.`}
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
                API Key
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
                  aria-label={showKey ? "Hide key" : "Show key"}
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
                  Retry check
                </Button>
              )}
              <Button
                variant="secondary"
                onPress={() => void handleTest()}
                isDisabled={formStatus.kind === "busy" || !apiKey.trim()}
              >
                Test
              </Button>
              <Button
                variant="primary"
                onPress={() => void handleSave()}
                isDisabled={formStatus.kind === "busy" || !apiKey.trim()}
              >
                {formStatus.kind === "busy" ? "Saving…" : "Save key"}
              </Button>
            </div>
          </Modal.Body>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
