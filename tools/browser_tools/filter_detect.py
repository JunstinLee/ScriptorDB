from __future__ import annotations

import json

from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.filters")
_DATE_TYPES = ("date", "datetime-local", "month", "week")

# 语义读取：Playwright 负责找候选，这里读命名原料（label/aria/相邻文本）与控件状态。
_SEMANTIC_JS = """\
(el) => {
  if (el.dataset.scdbSeen) return null;
  el.dataset.scdbSeen = '1';
  const lb = el.id ? document.querySelector('label[for="' + CSS.escape(el.id) + '"]') : null;
  const wrap = el.closest('label');
  const labelText = ((lb && lb.textContent) || (wrap && wrap.textContent) || '').replace(/\\s+/g, ' ').trim();
  const prev = (() => { let n = el.previousSibling;
    while (n) { if (n.nodeType === 3) { const t = n.textContent.replace(/\\s+/g, ' ').trim(); if (t) return t; } n = n.previousSibling; }
    const p = el.previousElementSibling; return p && p.children.length === 0 ? (p.textContent || '').trim() : ''; })();
  const vis = (() => { const r = el.getClientRects(); if (!r.length) return false;
    const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0; })();
  const tag = el.tagName.toLowerCase();
  const parent = el.parentElement;
  return {
    tag, type: el.getAttribute('type') || '', nameAttr: el.getAttribute('name') || '',
    ariaLabel: el.getAttribute('aria-label') || '', labelText, prev,
    placeholder: el.getAttribute('placeholder') || '', text: (el.textContent || '').trim().slice(0, 60),
    visible: vis, disabled: !!el.disabled, value: el.value || '', checked: !!el.checked,
    multiple: !!el.multiple, min: el.min || '', max: el.max || '', step: el.step || '',
    pressed: el.getAttribute('aria-pressed'),
    options: tag === 'select' ? Array.from(new Set(Array.from(el.options).map(o => o.textContent.trim()).filter(Boolean))) : null,
    parentKey: parent ? parent.tagName.toLowerCase() + (parent.id ? '#' + parent.id : '')
      + (parent.className ? '.' + String(parent.className).trim().split(/\\s+/).join('.') : '') : '',
  };
}
"""


async def _collect_candidates(page, include_hidden: bool) -> list[dict]:
    locs = [
        ("combobox", page.get_by_role("combobox")),
        ("checkbox", page.get_by_role("checkbox")),
        ("radio", page.get_by_role("radio")),
        ("slider", page.get_by_role("slider")),
        ("textbox", page.get_by_role("textbox")),
        ("searchbox", page.get_by_role("searchbox")),
        ("tags", page.get_by_role("button", pressed=True)),
        ("column", page.get_by_role("columnheader")),
    ]
    out = []
    for kind, loc in locs:
        try:
            items = await loc.evaluate_all(_SEMANTIC_JS)
        except Exception as e:
            logger.debug("filter candidates skipped (%s): %s", kind, e)
            continue
        for i, item in enumerate(items or []):
            if isinstance(item, dict) and (include_hidden or item.get("visible", True)):
                item["_kind"] = kind
                item["_index"] = i
                out.append(item)
    return out


_NAME_KEYS = ("labelText", "ariaLabel", "prev", "placeholder", "text")


def _name(item: dict, fallback: str) -> str:
    for k in _NAME_KEYS:
        v = (item.get(k) or "").strip()
        if v:
            return v[:60]
    return fallback


def _build_filters(items: list[dict], max_filters: int) -> list[dict]:
    filters: list[dict] = []
    groups: dict[tuple, dict] = {}
    dates: list[dict] = []

    def push(rec: dict) -> None:
        if len(filters) < max_filters:
            filters.append(rec)

    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item["_kind"]
        if kind in ("textbox", "searchbox"):
            if item["type"] in _DATE_TYPES:
                dates.append(item)
        elif kind == "combobox":
            push({"name": _name(item, "Unnamed filter"),
                  "type": "select" if item["tag"] == "select" else "combobox",
                  "options": item.get("options") or [],
                  "current": item.get("value", ""),
                  "multiple": bool(item.get("multiple"))})
        elif kind in ("checkbox", "radio", "tags"):
            # 统一分组：checkbox/radio 按 name，tags 按父容器
            key = (kind, item.get("nameAttr") or item.get("parentKey") or f"anon:{item['_index']}")
            g = groups.setdefault(key, {"name": _name(item, "Filter"), "type": kind,
                                        "options": [], "current": [], "members": []})
            label = (item.get("labelText") or item.get("prev") or item.get("text") or "").strip()
            active = item.get("checked") if kind != "tags" else str(item.get("pressed")) == "true"
            if label and label not in g["options"]:
                g["options"].append(label)
            if active:
                g["current"].append(label or item.get("value") or "")
            if label:
                g["members"].append(label)
        elif kind == "slider":
            push({"name": _name(item, "Range"), "type": "slider",
                  "min": item.get("min", ""), "max": item.get("max", ""), "step": item.get("step", ""),
                  "current": item.get("value", "")})
        else:  # column
            push({"name": (item.get("text") or "Column").strip().split()[0] + " filter",
                  "type": "table_column", "current": ""})

    for g in groups.values():
        push(g)

    # date_range 配对：同父容器相邻的两个日期输入
    paired: set[int] = set()
    i = 0
    while i + 1 < len(dates):
        a, b = dates[i], dates[i + 1]
        if a.get("parentKey") and a.get("parentKey") == b.get("parentKey"):
            push({"name": _name(a, "Date range"), "type": "date_range",
                  "current": [a.get("value", ""), b.get("value", "")]})
            paired.update((id(a), id(b)))
            i += 2
        else:
            i += 1
    for d in dates:
        if id(d) not in paired:
            push({"name": _name(d, "Date"), "type": "date", "current": d.get("value", "")})
    return filters


# ---- L2：JS 表格 / 框架公开 API 探测 ----
# 探测注册表：新增框架 = 追加一个探测函数（自包含特征检测 + 公开 API 读取 +
# capability 调用模板构造）；探测失败仅跳过自身，不影响其他层与其他探测。

_TABULATOR_PROBE_JS = """\
() => {
  const root = document.querySelector('.tabulator');
  if (!root) return [];
  if (!(window.Tabulator && typeof Tabulator.findTable === 'function')) return [];
  let inst = null;
  try { inst = Tabulator.findTable(root)[0] || null; } catch (e) { return []; }
  if (!inst) return [];
  let cols = [];
  try { cols = inst.getColumns ? inst.getColumns() : []; } catch (e) { return []; }
  let cur = [];
  try { cur = inst.getFilters ? inst.getFilters() : []; } catch (e) {}
  const currentByField = {};
  for (const f of cur) {
    if (f && typeof f === 'object' && f.field != null) currentByField[f.field] = f.value;
  }
  const out = [];
  for (const col of cols) {
    let def = null;
    try { def = col.getDefinition ? col.getDefinition() : null; } catch (e) {}
    if (!def) continue;
    const field = (def.field || '').toString();
    const title = (def.title || field || '').toString().trim();
    if (!title || !field) continue;
    let opts = [];
    const hfp = def.headerFilterParams;
    if (hfp && Array.isArray(hfp.values)) {
      opts = hfp.values
        .map(v => (v && typeof v === 'object' && 'label' in v) ? String(v.label) : String(v))
        .filter(Boolean);
    }
    out.push({
      name: title.slice(0, 60),
      field: field,
      options: Array.from(new Set(opts)),
      current: currentByField[field] != null ? String(currentByField[field]) : '',
    });
  }
  return out;
}
"""


def _build_tabulator_filters(raw: list, max_filters: int = 20) -> list[dict]:
    """Tabulator 探测结果 → js_table 条目（纯函数，可单测）。

    每列即一个可经 setFilter 公开 API 筛选的能力；capability.call 为探测端用
    公开 API 构造的调用模板（框架知识只存在于此处），apply 只做占位符替换。
    """
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or len(out) >= max_filters:
            continue
        field = (item.get("field") or "").strip()
        name = (item.get("name") or "").strip() or "Unnamed filter"
        call = (
            "Tabulator.findTable(document.querySelector('.tabulator'))[0]"
            f".setFilter({json.dumps(field)}, '=', $value)"
        )
        out.append({
            "name": name[:60],
            "type": "select",
            "options": [str(o) for o in (item.get("options") or []) if str(o).strip()],
            "current": str(item.get("current", "") or ""),
            "capability": {
                "kind": "set_filter",
                "field": field,
                "call": call,
                "value_placeholder": "$value",
            },
        })
    return out


async def _probe_tabulator(page) -> list[dict]:
    raw = await page.evaluate(_TABULATOR_PROBE_JS)
    return _build_tabulator_filters(raw or [])


_FRAMEWORK_PROBES = [
    _probe_tabulator,
]


async def _detect_js_table(page) -> list[dict]:
    """L2 探测：遍历框架探测注册表，合并命中条目的原始结果。"""
    entries: list[dict] = []
    for probe in _FRAMEWORK_PROBES:
        try:
            entries.extend(await probe(page))
        except Exception as e:
            logger.debug("js table probe skipped: %s", e)
    return entries


async def _detect_filters(page, include_hidden: bool, max_filters: int) -> list[dict]:
    """检测管线：L1 DOM 控件 + L2 JS 表格/框架能力 → 统一 Filter Schema 条目。

    与工具入口（_require_browser / record_action / 返回结构）解耦；
    新增框架探测 = 向 _FRAMEWORK_PROBES 追加探测函数。
    """
    cap = max(max_filters, 1)
    filters: list[dict] = []
    for f in _build_filters(await _collect_candidates(page, include_hidden), cap):
        filters.append({**f, "source": "dom", "mechanism": "dom_action"})
    for entry in await _detect_js_table(page):
        if not isinstance(entry, dict):
            continue
        filters.append({**entry, "source": "js_table", "mechanism": "js_table_api"})
    return filters[:cap]


@db_tool(name="browser_detect_filters", category="browser", timeout=15, sequential=False)
async def browser_detect_filters(
    ctx: RunContext[Settings],
    include_hidden: bool = False,
    max_filters: int = 20,
) -> dict:
    """识别页面筛选组件，返回 Filter Schema（name/type/options/current）。name 可直接作为 browser_apply_filter 的 target。"""
    manager, page_obj = _require_browser()
    if page_obj is None:
        return {"error": "Browser not launched. Please call browser_launch first."}
    if blocked := _check_blocked(manager):
        return {"error": blocked}
    try:
        filters = await _detect_filters(page_obj, include_hidden, max_filters)
    except Exception as e:
        manager.record_action("detect_filters", f"error: {e}", success=False)
        return {"error": f"Filter detection failed: {e}"}
    finally:
        try:
            await page_obj.evaluate(
                "() => document.querySelectorAll('[data-scdb-seen]').forEach(el => delete el.dataset.scdbSeen)"
            )
        except Exception:
            pass
    manager.record_action("detect_filters", f"{len(filters)} filters")
    return {"url": page_obj.url, "count": len(filters), "filters": filters}
