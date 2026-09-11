/** browser_apply_filter 支持的筛选动作（与 FILTER_ACTIONS 对齐） */
export type FilterActionType =
  | "select"
  | "input"
  | "toggle"
  | "set_range"
  | "date_range";

/** browser_detect_filters 返回的单个筛选器（Filter Schema 条目） */
export interface FilterSchemaItem {
  name: string;
  type:
    | "select"
    | "combobox"
    | "checkbox"
    | "radio"
    | "tags"
    | "slider"
    | "table_column"
    | "date_range"
    | "date";
  options?: string[];
  current?: string | string[];
  multiple?: boolean;
  min?: string;
  max?: string;
  step?: string;
}

/** browser_detect_filters 返回的 Filter Schema */
export interface FilterSchema {
  url: string;
  count: number;
  filters: FilterSchemaItem[];
}

/** 确认抽屉/面板组装的应用参数（与 browser_apply_filter 参数同名） */
export interface FilterOverrideActions {
  action: FilterActionType;
  target: string;
  value?: string;
  values?: string;
  submit?: boolean;
}
