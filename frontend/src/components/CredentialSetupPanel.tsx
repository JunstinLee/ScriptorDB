import { useState } from "react";
import { KeyRound, Save, Trash2 } from "lucide-react";
import { saveCredentials, deleteCredentials } from "../api/loginCredentials";
import type { CredentialStatus, ExtraCandidate, ExtraPlacement } from "../types";

export interface CredentialSetupPanelProps {
  /** 当前登录页 netloc（父组件由 login_form.url 推导） */
  site: string;
  /** 保存时所在页面 URL（login_form.url），随保存请求提交 */
  url: string;
  /** 预填主账号（非敏感），默认 "" */
  username?: string;
  /** 本 site 是否已配置（父组件传入，组件不自查） */
  configured: boolean;
  /** 页面检测到的第三项候选（DOM 序 + 落位）；空数组 = 该页无第三项，不渲染 */
  fieldCandidates: ExtraCandidate[];
  /** 保存成功后回调（父组件用来翻转 configured + 关闭面板） */
  onSaved?: (status: CredentialStatus) => void;
  /** 删除成功后回调 */
  onDeleted?: (site: string) => void;
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
  const [extraValue, setExtraValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // 第三项（可选项）完全由页面内容决定：取 DOM 序首个候选，无候选则不显示。
  const extraCandidate: ExtraCandidate | null = fieldCandidates[0] ?? null;
  const extraHint = extraCandidate
    ? [extraCandidate.label, extraCandidate.placeholder, extraCandidate.name]
        .filter(Boolean)
        .join(" · ")
    : "";
  // 保存用的字段名（field_label）：页面标注 → placeholder → name → selector 兜底。
  const extraLabel = extraCandidate
    ? extraCandidate.label ||
      extraCandidate.placeholder ||
      extraCandidate.name ||
      extraCandidate.selector
    : "";
  // 落位：页面 DOM 序派生（账号之上 / 账号与密码之间 / 密码之下）。
  const placement: ExtraPlacement = extraCandidate?.placement ?? "after";

  const resetInputs = () => {
    setMainUsername("");
    setPassword("");
    setExtraValue("");
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
    // 可选项：仅当页面检测到第三项且用户填写了值才随凭证保存（留空 = 不保存该槽位）。
    const extra =
      extraCandidate && extraValue
        ? {
            field_label: extraLabel,
            value: extraValue,
            match_hints: {
              name: extraCandidate.name ?? "",
              id: extraCandidate.id ?? "",
              label: extraCandidate.label ?? "",
              placeholder: extraCandidate.placeholder ?? "",
            },
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

  // 第三项（可选项）：单个输入框，落位与是否出现由页面内容决定。
  const extraBlock = extraCandidate && (
    <input
      type="text"
      value={extraValue}
      onChange={(e) => setExtraValue(e.target.value)}
      placeholder={extraHint ? `${extraHint} (optional)` : "Extra login info (optional)"}
      autoComplete="off"
      className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
    />
  );

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
        {placement === "before" && extraBlock}
        <input
          type="text"
          value={mainUsername}
          onChange={(e) => setMainUsername(e.target.value)}
          placeholder="Account name"
          autoComplete="off"
          className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />
        {placement === "between" && extraBlock}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoComplete="new-password"
          className="rounded-lg border border-grid bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />
        {placement === "after" && extraBlock}

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
