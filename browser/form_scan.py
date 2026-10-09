"""表单控件扫描的共享 JS 片段。

登录页提取（``browser.login_form``）、``browser_read`` 的表单读、以及点击后的
状态快照（``tools.browser_common._CLICK_SNAPSHOT_JS``）共用同一份「不调用的
函数源片段」：各方在自己的 IIFE 里内联该片段，再调用 ``__scanFormControls()``。
"""

from __future__ import annotations

# 不调用的函数源片段：定义 __scanFormControls()，返回全页表单控件的结构化元数据
# （label / 全页唯一选择器 / type / name / id / placeholder / value，select 附 options）。
FORM_SCAN_SNIPPET = """\
  const __formVisible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return cs.display !== "none" && cs.visibility !== "hidden"
      && r.width > 0 && r.height > 0;
  };
  const __formTextOf = (el) => (el.textContent || "").replace(/\\s+/g, " ").trim();
  const __formLabelFor = (el) => {
    if (el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) return __formTextOf(l);
    }
    const wrap = el.closest("label");
    if (wrap) return __formTextOf(wrap);
    const aria = el.getAttribute("aria-label");
    if (aria) return aria.trim();
    if (el.labels && el.labels.length) return __formTextOf(el.labels[0]);
    return "";
  };
  const __formCountMatches = (sel) => {
    try { return document.querySelectorAll(sel).length; } catch (e) { return 0; }
  };
  const __formSelectorFor = (el) => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase();
    const base = tag === "input" && type
      ? tag + '[type=' + JSON.stringify(type) + ']' : tag;
    if (el.id) {
      const byId = "#" + CSS.escape(el.id);
      if (__formCountMatches(byId) === 1) return byId;
    }
    const name = el.getAttribute("name");
    if (name) {
      const byName = base + '[name=' + JSON.stringify(name) + ']';
      if (__formCountMatches(byName) === 1) return byName;
    }
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const nodeTag = node.tagName.toLowerCase();
      const nodeType = (node.getAttribute("type") || "").toLowerCase();
      let part = nodeTag === "input" && nodeType
        ? nodeTag + '[type=' + JSON.stringify(nodeType) + ']' : nodeTag;
      const parent = node.parentElement;
      if (parent) {
        const sameTag = Array.from(parent.children)
          .filter((c) => c.tagName === node.tagName);
        if (sameTag.length > 1) {
          part += ":nth-of-type(" + (sameTag.indexOf(node) + 1) + ")";
        }
      }
      parts.unshift(part);
      const candidate = parts.join(" > ");
      if (__formCountMatches(candidate) === 1) return candidate;
      if (parent === null || parent === document.documentElement) break;
      node = parent;
    }
    return parts.join(" > ") || base;
  };
  const __scanFormControls = () => {
    const controls = [];
    const seen = new Set();
    const push = (el, inForm) => {
      if (seen.has(el)) return;
      seen.add(el);
      const tag = el.tagName.toLowerCase();
      const rec = {
        tag: tag,
        type: (el.getAttribute("type") || "").toLowerCase(),
        name: el.getAttribute("name") || "",
        id: el.id || "",
        placeholder: el.getAttribute("placeholder") || "",
        autocomplete: el.getAttribute("autocomplete") || "",
        required: !!el.required,
        label: __formLabelFor(el),
        text: __formTextOf(el),
        selector: __formSelectorFor(el),
        visible: __formVisible(el),
        in_form: inForm,
        value: (el.value === undefined || el.value === null) ? "" : String(el.value),
      };
      if (tag === "select") {
        rec.options = Array.from(el.options || []).map((o) => ({
          value: String(o.value),
          label: __formTextOf(o),
          selected: !!o.selected,
        }));
      } else if (tag === "input" && (rec.type === "checkbox" || rec.type === "radio")) {
        rec.checked = !!el.checked;
      }
      controls.push(rec);
    };
    const forms = Array.from(document.querySelectorAll("form"));
    if (forms.length) {
      forms.forEach((form) => {
        form.querySelectorAll("input, select, textarea, button")
          .forEach((el) => push(el, true));
      });
    } else {
      document.querySelectorAll("input, select, textarea, button")
        .forEach((el) => push(el, false));
    }
    return controls;
  };
"""


def extract_form_js() -> str:
    """``() => [...controls]`` 形式的完整脚本（登录页提取 / browser_read 表单读用）。"""
    return "() => {\n" + FORM_SCAN_SNIPPET + "  return __scanFormControls();\n}"
