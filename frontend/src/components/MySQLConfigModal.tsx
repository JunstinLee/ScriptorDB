import { useCallback, useEffect, useState } from "react";
import { Button, Input, Label, ListBox, Modal, Select, Switch, toast } from "@heroui/react";
import { Database, Server, CheckCircle2, AlertCircle, Eye, EyeOff } from "lucide-react";
import { configureMySQL, resetMySQLConfig } from "../api/workspaces";
import { t } from "../i18n";
import type { MySQLConfigRequest, MySQLConfigResponse, WorkspaceDetail } from "../types";

interface MySQLConfigModalProps {
  workspace: WorkspaceDetail | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onConfigSaved?: () => void;
}

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 3306;
const DEFAULT_USER = "root";

function parseInitialValues(workspace: WorkspaceDetail | null): MySQLConfigRequest {
  if (!workspace) {
    return { host: DEFAULT_HOST, port: DEFAULT_PORT, user: DEFAULT_USER, db: "", password: "", test_first: true };
  }
  const key = `mysql_pwd_${workspace.id}`;
  return {
    host: workspace.mysql_host ?? DEFAULT_HOST,
    port: workspace.mysql_port ?? DEFAULT_PORT,
    user: workspace.mysql_user ?? DEFAULT_USER,
    db: workspace.mysql_db ?? "",
    password: localStorage.getItem(key) || "",
    test_first: true,
  };
}

function isMySQLUrl(dbUrl: string | undefined): boolean {
  return !!dbUrl && dbUrl.startsWith("mysql+pymysql://");
}

type Engine = "sqlite" | "mysql";

function getEngineFromUrl(dbUrl: string | undefined): Engine {
  return isMySQLUrl(dbUrl) ? "mysql" : "sqlite";
}

export default function MySQLConfigModal({
  workspace,
  isOpen,
  onOpenChange,
  onConfigSaved,
}: MySQLConfigModalProps) {
  const [form, setForm] = useState<MySQLConfigRequest>(parseInitialValues(workspace));
  const [engine, setEngine] = useState<Engine>(() => getEngineFromUrl(workspace?.db_url));
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<MySQLConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setEngine(getEngineFromUrl(workspace?.db_url));
      setForm(parseInitialValues(workspace));
      setResult(null);
      setError(null);
    }
  }, [isOpen, workspace?.id]);

  const updateField = useCallback(<K extends keyof MySQLConfigRequest>(key: K, value: MySQLConfigRequest[K]) => {
    setForm((prev: MySQLConfigRequest) => ({ ...prev, [key]: value }));
    setResult(null);
    setError(null);
    if (key === "password" && workspace) {
      const key_ = `mysql_pwd_${workspace.id}`;
      if (value && typeof value === "string" && value.trim()) {
        localStorage.setItem(key_, value as string);
      } else {
        localStorage.removeItem(key_);
      }
    }
  }, [workspace]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!workspace) return;
      setBusy(true);
      setError(null);
      setResult(null);
      try {
        const res =
          engine === "sqlite"
            ? await resetMySQLConfig(workspace.id)
            : await configureMySQL(workspace.id, {
                ...form,
                port: Number(form.port) || DEFAULT_PORT,
              });
        if (!res.ok) {
          setError(`${res.message || t("database.connection_failed")}${res.error_code ? ` (${res.error_code})` : ""}`);
        } else {
          setResult(res);
          toast.success(engine === "mysql" ? t("database.toast_mysql") : t("database.toast_sqlite"));
          onConfigSaved?.();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message.replace(/^HTTP \d+: /, "") : t("database.save_failed"));
      } finally {
        setBusy(false);
      }
    },
    [engine, form, workspace, onConfigSaved],
  );

  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={onOpenChange}>
      <Modal.Container size="md" scroll="inside">
        <Modal.Dialog className="sm:max-w-130 max-h-[85vh] min-h-90 bg-surface">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Icon className="bg-accent-soft text-accent-soft-foreground">
              <Database className="size-5" />
            </Modal.Icon>
            <Modal.Heading>{t("database.connection_title")}</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <Label id="engine-label" className="text-xs text-graphite">{t("database.engine_label")}</Label>
                <Select
                  aria-labelledby="engine-label"
                  value={engine}
                  onChange={(v) => {
                    if (typeof v === "string") {
                      setEngine(v as Engine);
                      setResult(null);
                      setError(null);
                    }
                  }}
                >
                  <Select.Trigger>
                    <Select.Value />
                    <Select.Indicator />
                  </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    <ListBox.Item id="sqlite" textValue={t("database.engine_sqlite")}>
                      {t("database.engine_sqlite")}
                    </ListBox.Item>
                    <ListBox.Item id="mysql" textValue={t("database.engine_mysql")}>
                      {t("database.engine_mysql")}
                    </ListBox.Item>
                  </ListBox>
                </Select.Popover>
              </Select>
            </div>

              <form id="mysql-config-form" onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4">
                {engine === "sqlite" ? (
                  <div className="rounded-lg border border-grid bg-surface p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-ink">
                      <Database className="size-4 text-cobalt" />
                      {t("database.sqlite_title")}
                    </div>
                    <p className="mt-1 text-[11px] text-muted">
                      {t("database.sqlite_hint")}
                    </p>
                    {workspace?.db_url && (
                      <code className="mt-3 block truncate text-[11px] font-mono text-graphite">
                        {workspace.db_url}
                      </code>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="col-span-2 flex flex-col gap-1.5">
                        <Label htmlFor="mysql-host" className="text-xs text-graphite">
                          {t("database.host")}
                        </Label>
                        <Input
                          id="mysql-host"
                          value={form.host}
                          placeholder="127.0.0.1"
                          onChange={(e) => updateField("host", e.target.value)}
                          disabled={busy}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="mysql-port" className="text-xs text-graphite">
                          {t("database.port")}
                        </Label>
                        <Input
                          id="mysql-port"
                          type="number"
                          value={String(form.port)}
                          placeholder="3306"
                          onChange={(e) => updateField("port", Number(e.target.value))}
                          disabled={busy}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="mysql-user" className="text-xs text-graphite">
                          {t("database.user")}
                        </Label>
                        <Input
                          id="mysql-user"
                          value={form.user}
                          placeholder="root"
                          onChange={(e) => updateField("user", e.target.value)}
                          disabled={busy}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="mysql-db" className="text-xs text-graphite">
                          {t("database.name_label")}
                        </Label>
                        <Input
                          id="mysql-db"
                          value={form.db}
                          placeholder="scriptordb"
                          onChange={(e) => updateField("db", e.target.value)}
                          disabled={busy}
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="mysql-password" className="text-xs text-graphite">
                        {t("database.password")}
                      </Label>
                      <div className="relative">
                        <Input
                          id="mysql-password"
                          type={showPassword ? "text" : "password"}
                          value={form.password}
                          placeholder={workspace?.mysql_password_set ? t("database.password_keep_placeholder") : ""}
                          onChange={(e) => updateField("password", e.target.value)}
                          disabled={busy}
                          className="w-full pr-8"
                        />
                        <button
                          type="button"
                          className="absolute inset-y-0 right-2 flex items-center justify-center text-graphite hover:text-ink"
                          onClick={() => setShowPassword(!showPassword)}
                          tabIndex={-1}
                        >
                          {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                        </button>
                      </div>
                      <p className="text-[11px] text-muted">
                        {t("database.keyring_hint")}
                      </p>
                    </div>

                    <div className="flex items-center justify-between rounded-md border border-grid px-3 py-2">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-medium text-ink">{t("database.test_first")}</span>
                        <span className="text-[11px] text-muted">{t("database.test_first_hint")}</span>
                      </div>
                      <Switch
                        isSelected={form.test_first ?? true}
                        onChange={(v) => updateField("test_first", v)}
                        isDisabled={busy}
                      >
                        <Switch.Control>
                          <Switch.Thumb />
                        </Switch.Control>
                      </Switch>
                    </div>
                  </>
                )}
              </form>

              {result?.ok && !error && (
                <div className="flex items-start gap-2 rounded-lg border border-sage/30 bg-sage/10 p-3">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-sage" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-ink">{t("database.connected")}</span>
                    <span className="text-[11px] font-mono text-graphite">{result.db_url}</span>
                  </div>
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-vermilion/30 bg-vermilion/10 p-3">
                  <AlertCircle className="mt-0.5 size-4 shrink-0 text-vermilion" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-ink">{t("database.connection_failed")}</span>
                    <span className="text-[11px] text-graphite">{error}</span>
                  </div>
                </div>
              )}
            </div>
          </Modal.Body>
          <Modal.Footer className="flex justify-end">
            <Button
              type="submit"
              form="mysql-config-form"
              variant="primary"
              isDisabled={busy || !workspace || (engine === "mysql" && !form.db.trim())}
            >
              <Server className="mr-1.5 size-3.5" />
              {busy ? t("database.saving") : engine === "sqlite" ? t("database.use_sqlite") : t("database.test_and_save")}
            </Button>
          </Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
