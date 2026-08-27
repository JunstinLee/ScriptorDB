import { useMemo, useState } from "react";
import { Button, Input, Label, ListBox, Select, Switch } from "@heroui/react";
import type {
  ApprovalRequestEvent,
  FilterActionType,
  FilterOverrideActions,
  FilterSchema,
  FilterSchemaItem,
} from "../types";

interface FilterConfirmDrawerProps {
  request: ApprovalRequestEvent;
  schema: FilterSchema | null;
  onApprove: (overrideArgs: Record<string, Record<string, unknown>>) => void;
  onReject: () => void;
}

/** schema 类型 → browser_apply_filter 动作映射（无对应动作返回 null） */
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
    default:
      return null;
  }
}

function parseValues(raw: unknown): string[] {
  try {
    const parsed = typeof raw === "string" && raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) && parsed.length === 2
      ? [String(parsed[0]), String(parsed[1])]
      : ["", ""];
  } catch {
    return ["", ""];
  }
}

export function FilterConfirmDrawer({
  request,
  schema,
  onApprove,
  onReject,
}: FilterConfirmDrawerProps) {
  const call = request.calls[0];
  const plan = (call?.args ?? {}) as Partial<FilterOverrideActions>;

  const [action, setAction] = useState<FilterActionType>(
    (plan.action as FilterActionType) ?? "select",
  );
  const [target, setTarget] = useState(plan.target ?? "");
  const [value, setValue] = useState(plan.value ?? "");
  const [values, setValues] = useState<string[]>(() => parseValues(plan.values));
  const [submit, setSubmit] = useState(plan.submit ?? true);

  // 当前 target 在 schema 中的条目（提供 options/current 等）
  const schemaItem = useMemo(
    () => (schema?.filters ?? []).find((f) => f.name === target) ?? null,
    [schema, target],
  );
  // "选择其他"候选：schema 中映射为同一 action 的其余筛选器
  const candidates = useMemo(
    () =>
      (schema?.filters ?? []).filter(
        (f) => typeToAction(f.type) === action && f.name !== target,
      ),
    [schema, action, target],
  );
  const options = schemaItem?.options ?? [];

  const handleApply = () => {
    const changed: Record<string, unknown> = {};
    if (action !== ((plan.action as FilterActionType) ?? "select")) {
      changed.action = action;
    }
    if (target !== (plan.target ?? "")) {
      changed.target = target;
    }
    if (action === "date_range") {
      const next = JSON.stringify(values);
      if (next !== (plan.values ?? "[]")) changed.values = next;
    } else if (value !== (plan.value ?? "")) {
      changed.value = value;
    }
    if (submit !== (plan.submit ?? true)) {
      changed.submit = submit;
    }
    const override: Record<string, Record<string, unknown>> = {};
    if (Object.keys(changed).length > 0 && call) {
      override[call.tool_call_id] = changed;
    }
    onApprove(override);
  };

  const renderActionControl = () => {
    switch (action) {
      case "select":
        if (options.length > 0) {
          return (
            <Select
              className="w-full"
              value={value}
              onChange={(v) => {
                if (typeof v === "string") setValue(v);
              }}
            >
              <Label>选项</Label>
              <Select.Trigger>
                <Select.Value />
                <Select.Indicator />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  {options.map((opt) => (
                    <ListBox.Item key={opt} id={opt} textValue={opt}>
                      {opt}
                    </ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select>
          );
        }
        // 降级：无 options（schema 缺失/无候选）→ 自由填值
        return (
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="输入选项值"
          />
        );
      case "input":
      case "set_range":
        return (
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={
              action === "set_range" ? "如 30" : "输入筛选文本后回车"
            }
          />
        );
      case "date_range":
        return (
          <div className="flex items-center gap-2">
            <input
              type="date"
              className="h-9 rounded-lg border border-grid bg-background px-2 text-sm text-foreground"
              value={values[0] ?? ""}
              onChange={(e) =>
                setValues((prev) => [e.target.value, prev[1] ?? ""])
              }
            />
            <span className="text-xs text-muted">至</span>
            <input
              type="date"
              className="h-9 rounded-lg border border-grid bg-background px-2 text-sm text-foreground"
              value={values[1] ?? ""}
              onChange={(e) =>
                setValues((prev) => [prev[0] ?? "", e.target.value])
              }
            />
          </div>
        );
      case "toggle":
        return (
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={String(value).toLowerCase() === "true"}
              onChange={(e) => setValue(e.target.checked ? "true" : "false")}
              className="size-4 accent-[var(--accent)]"
            />
            <span className="text-muted">勾选该选项</span>
          </label>
        );
      default:
        return null;
    }
  };

  return (
    <div className="border-t border-grid bg-surface px-4 py-4">
      <div className="mb-3">
        <p className="text-sm font-semibold text-foreground">确认筛选操作</p>
        <p className="mt-0.5 text-xs text-muted">
          {call?.tool_name ?? "browser_apply_filter"} · {target || "未命名筛选器"}
          {schemaItem ? `（${schemaItem.type}）` : ""}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-muted">动作</span>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as FilterActionType)}
            className="h-9 flex-1 rounded-lg border border-grid bg-background px-2 text-sm text-foreground"
          >
            <option value="select">select（下拉）</option>
            <option value="input">input（文本）</option>
            <option value="toggle">toggle（勾选）</option>
            <option value="set_range">set_range（滑块）</option>
            <option value="date_range">date_range（日期区间）</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-muted">筛选器</span>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="h-9 flex-1 rounded-lg border border-grid bg-background px-2 text-sm text-foreground"
            placeholder="筛选器 name 或 selector"
          />
        </div>

        {candidates.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-xs text-muted">选择其他</span>
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) setTarget(e.target.value);
              }}
              className="h-9 flex-1 rounded-lg border border-grid bg-background px-2 text-sm text-foreground"
            >
              <option value="" disabled>
                同类型筛选器…
              </option>
              {candidates.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-muted">值</span>
          <div className="flex-1">{renderActionControl()}</div>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-muted">提交</span>
          <Switch
            isSelected={submit}
            onChange={setSubmit}
            size="sm"
          >
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
          </Switch>
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onPress={onReject}>
          拒绝
        </Button>
        <Button variant="primary" size="sm" onPress={handleApply}>
          应用
        </Button>
      </div>
    </div>
  );
}
