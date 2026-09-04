import { useState } from "react";
import { ChevronDown, KeyRound, Save, Trash2 } from "lucide-react";
import { saveCredentials, deleteCredentials } from "../api/loginCredentials";
import type { CredentialStatus, LoginFieldInfo } from "../types";

export interface CredentialSetupPanelProps {
  /** 当前登录页 netloc（父组件由 login_form.url 推导） */
  site: string;
  /** 保存时所在页面 URL（login_form.url），随保存请求提交 */
  url: string;
  /** 预填主账号（非敏感），默认 "" */
  username?: string;
  /** 本 site 是否已配置（父组件传入，组件不自查） */
  configured: boolean;
  /** unknown 可填字段候选（父组件从 login_form.fields 过滤后传入；无则传 []） */
  fieldCandidates: LoginFieldInfo[];
  /** 保存成功后回调（父组件用来翻转 configured + 关闭面板） */
  onSaved?: (status: CredentialStatus) => void;
  /** 删除成功后回调 */
  onDeleted?: (site: string) => void;
}

function hintText(field: LoginFieldInfo): string {
  return [field.label, field.placeholder, field.name]
    .filter((x): x is string => Boolean(x))
    .join(" · ");
}

/** 凭证采集表单：首次保存登录信息到系统密钥（Keychain/CM/Secret Service）。 */
export function CredentialSetupPanel({
  site,
  url,
  username = "",
  configured,
  fieldCandidates,
  onSaved,
  onDeleted,
}: CredentialSetupPanelProps) {
  const [mainUsername, setMainUsername] = useState(username);
  const [password, setPassword] = useState("");
  const [extraOpen, setExtraOpen] = useState(false);
  const [fieldLabel, setFieldLabel] = useState("");
  const [extraValue, setExtraValue] = useState("");
  const [selectedField, setSelectedField] = useState<LoginFieldInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const resetInputs = () => {
    setMainUsername("");
    setPassword("");
    setFieldLabel("");
    setExtraValue("");
    setSelectedField(null);
    setExtraOpen(false);
    setError("");
  };

  const handleSave = async () => {
    setError("");
    if (!mainUsername.trim()) {
      setError("Please fill in the account name");
      return;
    }
    if (!password) {
      setError("Please fill in the password");
      return;
    }
    const extraPartial =
      fieldLabel.trim().length > 0 || extraValue.length > 0;
    if (extraPartial && (!fieldLabel.trim() || !extraValue)) {
      setError("Both field name and value are required for extra login info");
      return;
    }

    const extra = extraPartial
      ? {
          field_label: fieldLabel.trim(),
          value: extraValue,
          match_hints: selectedField
            ? {
                name: selectedField.name ?? "",
                id: selectedField.id ?? "",
                label: selectedField.label ?? "",
                placeholder: selectedField.placeholder ?? "",
              }
            : null,
        }
      : null;

    setSaving(true);
    try {
      const status = await saveCredentials({
        site,
        url,
        username: mainUsername.trim(),
        password,
        extra,
      });
      resetInputs();
      onSaved?.(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save credentials");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setError("");
    setSaving(true);
    try {
      await deleteCredentials(site);
      resetInputs();
      onDeleted?.(site);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete credentials");
    } finally {
      setSaving(false);
    }
  };

  const handleFieldSelect = (value: string) => {
    const field = fieldCandidates.find((f) => f.selector === value) ?? null;
    setSelectedField(field);
    if (field) {
      setFieldLabel(field.label || field.placeholder || field.name || "");
    }
  };

  return (
    <div className="rounded-xl border border-grid bg-surface px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <KeyRound className="size-4 text-accent" />
        <p className="text-sm font-semibold text-foreground">
          {configured ? "Reconfigure saved login info" : "Save login info for this site"}
        </p>
        {configured && (
          <button
            onClick={handleDelete}
            disabled={saving}
            title="Delete saved login info"
            className="ml-auto inline-flex items-center gap-1 rounded-lg border border-grid px-2 py-1 text-[11px] text-muted hover:bg-danger/10 hover:text-danger"
          >
            <Trash2 className="size-3" />
            Delete
          </button>
        )}
      </div>

      {!configured && site && (
        <p className="mb-3 truncate font-mono text-[11px] text-muted">{site}</p>
      )}

      <div className="flex flex-col gap-2">
        <input
          type="text"
          value={mainUsername}
          onChange={(e) => setMainUsername(e.target.value)}
          placeholder="Account name"
          autoComplete="off"
          className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoComplete="new-password"
          className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />

        <div className="rounded-lg border border-grid">
          <button
            onClick={() => setExtraOpen((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-muted hover:bg-surface/60"
          >
            <span>Extra login info (optional)</span>
            <ChevronDown
              className={`size-3.5 transition-transform ${extraOpen ? "rotate-180" : ""}`}
            />
          </button>
          {extraOpen && (
            <div className="flex flex-col gap-2 border-t border-grid px-3 py-2">
              <input
                type="text"
                value={fieldLabel}
                onChange={(e) => setFieldLabel(e.target.value)}
                placeholder="Field name, e.g. User ID / Account ID / employee no."
                autoComplete="off"
                className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
              />
              <input
                type="text"
                value={extraValue}
                onChange={(e) => setExtraValue(e.target.value)}
                placeholder="Value"
                autoComplete="off"
                className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
              />
              {fieldCandidates.length > 0 && (
                <select
                  value={selectedField?.selector ?? ""}
                  onChange={(e) => handleFieldSelect(e.target.value)}
                  className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
                >
                  <option value="">This extra info maps to… (optional)</option>
                  {fieldCandidates.map((f) => (
                    <option key={f.selector} value={f.selector}>
                      {hintText(f) || f.selector}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}

        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
          >
            <Save className="size-3.5" />
            {configured ? "Update" : "Save"}
          </button>
        </div>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted">
        Saved to the system keychain. Plaintext is never stored in the browser.
      </p>
    </div>
  );
}

export default CredentialSetupPanel;
