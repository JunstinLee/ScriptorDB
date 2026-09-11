from __future__ import annotations

import json

from core.logging_setup import get_logger

logger = get_logger("tools.browser.filters")

# ---- L2：JS 表格 / 框架公开 API 探测 ----
# 分层：先通用枚举页面全部表格根，再对每个根逐个执行框架探测。
# 通用层不含任何框架专属定位表达式；框架容器标记一律经探测注册表声明。
# 本模块是通用表格根枚举 + 框架探测注册表（framework registry）：
#   - filter_detect（L1 DOM + 合并管线）导入 FRAMEWORK_PROBES / TABLE_SELECTORS
#   - runtime/middleware_probe（tool_middleware 页面启发）导入 FRAMEWORK_PROBES
# 新增框架 = 在本模块注册表追加一项；探测失败仅跳过自身，不影响其他根与其他探测。

# 通用表格根标记（不含框架名）
_GENERIC_TABLE_SELECTORS = ("table", "[role=table]", "[role=grid]")

# 根枚举：收集全部候选根、去重、剔除嵌套在其他根内的根、按文档序编号，
# 为每个根写入稳定的 data-scdb-tableroot 属性并计算可读 label（就近标题/
# 表格标题/首行文本），供模型辨认目标表。
_COLLECT_ROOTS_JS = """\
(params) => {
  const els = [];
  for (const sel of params.selectors) {
    for (const el of document.querySelectorAll(sel)) els.push(el);
  }
  const seen = new Set();
  const uniq = [];
  for (const el of els) {
    if (seen.has(el)) continue;
    seen.add(el);
    uniq.push(el);
  }
  const roots = uniq.filter((el) => {
    let p = el.parentElement;
    while (p) {
      if (seen.has(p)) return false;
      p = p.parentElement;
    }
    return true;
  });
  roots.sort((a, b) => {
    const pos = a.compareDocumentPosition(b);
    return (pos & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1;
  });
  const labelFor = (el) => {
    if (el.tagName === 'TABLE' && el.caption && (el.caption.textContent || '').trim()) {
      return el.caption.textContent.trim().slice(0, 60);
    }
    let cur = el;
    for (let depth = 0; depth < 3; depth++) {
      let n = cur.previousElementSibling;
      while (n) {
        if (/^H[1-6]$/.test(n.tagName) && (n.textContent || '').trim()) {
          return n.textContent.trim().slice(0, 60);
        }
        n = n.previousElementSibling;
      }
      cur = cur.parentElement;
      if (!cur || cur === document.documentElement) break;
    }
    return '';
  };
  return roots.map((el, i) => {
    el.setAttribute('data-scdb-tableroot', String(i));
    return {
      index: i,
      selector: '[data-scdb-tableroot="' + i + '"]',
      label: labelFor(el),
    };
  });
}
"""


async def collect_table_roots(page, selectors: tuple[str, ...]) -> list[dict]:
    """通用表格根枚举：返回 [{index, selector, label}]，按文档序编号。"""
    raw = await page.evaluate(_COLLECT_ROOTS_JS, {"selectors": list(selectors)})
    return [r for r in raw or [] if isinstance(r, dict)]


_TABULATOR_PROBE_JS = """\
(params) => {
  const root = document.querySelector(params.root);
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


def tabulator_call(root_selector: str, field: str) -> str:
    """探测端构造：绑定根 selector 的 setFilter 调用模板（框架知识只存在于此处）。"""
    root_expr = f"document.querySelector({json.dumps(root_selector)})"
    return (
        f"(() => {{ const el = {root_expr}; if (!el) return; "
        f"const t = Tabulator.findTable(el)[0]; if (!t) return; "
        f"t.setFilter({json.dumps(field)}, '=', $value); }})()"
    )


async def probe_tabulator(page, root: dict) -> list[dict]:
    """按根探测（注册表项）：root 为 collect_table_roots 返回的表格身份。"""
    raw = await page.evaluate(_TABULATOR_PROBE_JS, {"root": root["selector"]})
    out = []
    for col in raw or []:
        if not isinstance(col, dict):
            continue
        field = (col.get("field") or "").strip()
        if not field:
            continue
        out.append({
            "name": (col.get("name") or field)[:60],
            "options": col.get("options") or [],
            "current": col.get("current") or "",
            "capability": {
                "kind": "set_filter",
                "field": field,
                "table_selector": root["selector"],
                "call": tabulator_call(root["selector"], field),
                "value_placeholder": "$value",
            },
        })
    return out


# 探测注册表：每项自报 root_marker（框架容器标记）+ 按根执行的探测函数。
# 新增框架 = 追加一项；探测失败仅跳过自身，不影响其他根与其他探测。
FRAMEWORK_PROBES: list[dict] = [
    {"root_marker": ".tabulator", "probe": probe_tabulator},
]

# 完整表格根选择器：通用标记 + 各框架容器标记（供 filter_detect 与 middleware 共用）。
TABLE_SELECTORS: tuple[str, ...] = _GENERIC_TABLE_SELECTORS + tuple(
    p["root_marker"] for p in FRAMEWORK_PROBES
)
