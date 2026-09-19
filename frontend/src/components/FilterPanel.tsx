import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Chip } from "@heroui/react";
import { SlidersHorizontal, Loader2 } from "lucide-react";
import { interactBrowser } from "../api/browser";
import type {
  FilterActionType,
  FilterSchema,
  FilterSchemaItem,
  InteractRequest,
} from "../types";

interface FilterPanelProps {
  schema: FilterSchema | null;
  isRunning: boolean;
  sessionId: string;
  onApplied?: () => void;
}

interface RowState {
  value: string;
  values: string[];
  checked: boolean;
}

/** schema 类型 → browser_apply_filter 动作映射 */
function typeToAction(type: FilterSchemaItem["type"]): FilterActionType | null {
  switch (type) {
    case "select":
    case "combobox":
      return "select";
    case "date_range":
      return "date_range";
    case "date":
      return "input";
    case "checkbox":
    case "radio":
    case "tags":
      return "toggle";
    case "slider":
      return "set_range";
    case "table_column":
      return "input";
    default:
      return null;
  }
}

function initialRow(item: FilterSchemaItem): RowState {
  const current = item.current;
  if (Array.isArray(current)) {
    if (item.type === "date_range") {
      return { value: "", values: [current[0] ?? "", current[1] ?? ""], checked: false };
    }
    return { value: "", values: [], checked: current.length > 0 };
  }
  return { value: current ?? "", values: [], checked: false };
}

function buildRows(schema: FilterSchema | null): FilterSchemaItem[] {
  if (!schema) return [];
  return (schema.filters ?? []).filter((f) => typeToAction(f.type) !== null);
}

export function FilterPanel({
  schema,
  isRunning,
  onApplied,
}: FilterPanelProps) {
  const { t } = useTranslation();
  const rows = buildRows(schema);
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // schema 变化时重置编辑状态（初值为页面当前值）
  useEffect(() => {
    const next: Record<string, RowState> = {};
    for (const item of rows) {
      next[item.name] = initialRow(item);
    }
    setRowStates(next);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema]);

  const setRow = useCallback((name: string, patch: Partial<RowState>) => {
    setRowStates((prev) => ({ ...prev, [name]: { ...prev[name], ...patch } }));
  }, []);

  const handleApply = useCallback(async () => {
    if (rows.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      for (let i = 0; i < rows.length; i++) {
        const item = rows[i];
        const st = rowStates[item.name];
        const action = typeToAction(item.type);
        if (!action || !st) continue;
        const req: InteractRequest = {
          action,
          target: item.name,
          submit: i === rows.length - 1,
        };
        if (action === "date_range") {
          req.values = JSON.stringify(st.values);
        } else if (action === "toggle") {
          req.value = st.checked ? "true" : "false";
        } else {
          req.value = st.value;
        }
        await interactBrowser(req);
      }
      onApplied?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("filter.apply_failed"));
    } finally {
      setBusy(false);
    }
  }, [rows, rowStates, onApplied, t]);

  const renderRowControl = (item: FilterSchemaItem, disabled: boolean) => {
    const st = rowStates[item.name];
    if (!st) return null;
    switch (item.type) {
      case "select":
      case "combobox":
        return (
          <select
            value={st.value}
            disabled={disabled}
            onChange={(e) => setRow(item.name, { value: e.target.value })}
            className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
          >
            {(item.options ?? []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        );
      case "date_range":
        return (
          <div className="flex flex-1 items-center gap-1.5">
            <input
              type="date"
              value={st.values[0] ?? ""}
              disabled={disabled}
              onChange={(e) =>
                setRow(item.name, { values: [e.target.value, st.values[1] ?? ""] })
              }
              className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
            />
            <span className="text-xs text-muted">{t("filter.range_to")}</span>
            <input
              type="date"
              value={st.values[1] ?? ""}
              disabled={disabled}
              onChange={(e) =>
                setRow(item.name, { values: [st.values[0] ?? "", e.target.value] })
              }
              className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
            />
          </div>
        );
      case "date":
        return (
          <input
            type="date"
            value={st.value}
            disabled={disabled}
            onChange={(e) => setRow(item.name, { value: e.target.value })}
            className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
          />
        );
      case "checkbox":
      case "radio":
      case "tags":
        return (
          <label className="flex flex-1 cursor-pointer items-center gap-2 text-sm disabled:opacity-50">
            <input
              type="checkbox"
              checked={st.checked}
              disabled={disabled}
              onChange={(e) => setRow(item.name, { checked: e.target.checked })}
              className="size-4 accent-[var(--accent)]"
            />
            <span className="text-xs text-muted">
              {st.checked ? t("filter.checked") : t("filter.unchecked")}
            </span>
          </label>
        );
      case "slider":
        return (
          <input
            value={st.value}
            disabled={disabled}
            onChange={(e) => setRow(item.name, { value: e.target.value })}
            className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
            placeholder={item.min ? `${item.min} ~ ${item.max}` : t("filter.slider_placeholder")}
          />
        );
      default:
        return (
          <input
            value={st.value}
            disabled={disabled}
            onChange={(e) => setRow(item.name, { value: e.target.value })}
            className="h-8 flex-1 rounded-md border border-grid bg-background px-2 text-sm text-foreground disabled:opacity-50"
            placeholder={t("filter.text_placeholder")}
          />
        );
    }
  };

  if (!schema) {
    return (
      <div className="border-b border-grid px-4 py-3">
        <p className="text-xs text-muted">
          {t("filter.guide")}
        </p>
      </div>
    );
  }

  return (
    <div className="border-b border-grid px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="size-3.5 text-muted" />
          {t("filter.title")}
        </p>
        {isRunning && (
          <span className="text-[11px] text-muted">{t("filter.read_only")}</span>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-muted">{t("filter.empty")}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((item) => (
            <div key={item.name} className="flex items-center gap-2">
              <span className="w-28 shrink-0 truncate text-xs text-foreground">
                {item.name}
              </span>
              <Chip size="sm" variant="soft" className="shrink-0">
                {t(`filter.type.${item.type}`)}
              </Chip>
              {renderRowControl(item, isRunning || busy)}
            </div>
          ))}
          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="primary"
              onPress={() => void handleApply()}
              isDisabled={isRunning || busy || rows.length === 0}
            >
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : null}
              {t("filter.apply")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
