from __future__ import annotations

# `browser.runtime.locate_elements` 第一段：一次 evaluate 完成布局初筛 + 信号抽取。
# 契约：这里只产出原始信号（selector / enabled / receivesEvents / inViewport /
# inActive / rect / visibility …），"可操作性三态"一律由 Python 侧的
# `_confirm_actionable` 判定，避免字段语义在两层之间漂移。
LOCATE_ELEMENTS_JS = r"""
(filters) => {
    const tagSel = [
        "a", "button", "input", "select", "textarea",
        "li", "div", "span", "td", "label",
        "[role='button']", "[role='link']", "[role='tab']",
        "[role='menuitem']", "[role='checkbox']", "[role='radio']",
        "[role='textbox']", "[role='combobox']", "[role='searchbox']",
        "[role='switch']", "[role='option']"
    ].join(",");
    const scope = filters.scope || "visible";
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    const laidOutCache = new WeakMap();
    const laidOut = (el) => {
        let v = laidOutCache.get(el);
        if (v !== undefined) return v;
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        v = !(cs.display === "none" || cs.visibility === "hidden" ||
              r.width <= 0 || r.height <= 0);
        laidOutCache.set(el, v);
        return v;
    };
    const structCache = new WeakMap();
    const structCount = (el) => {
        let v = structCache.get(el);
        if (v === undefined) {
            v = el.querySelectorAll(tagSel).length;
            structCache.set(el, v);
        }
        return v;
    };
    const visCache = new WeakMap();
    const visibleCount = (el) => {
        let v = visCache.get(el);
        if (v !== undefined) return v;
        let c = 0;
        for (const d of el.querySelectorAll(tagSel)) {
            if (laidOut(d)) c++;
        }
        visCache.set(el, c);
        return c;
    };
    const activeCache = new WeakMap();
    const isActiveContainer = (el) => {
        let v = activeCache.get(el);
        if (v !== undefined) return v;
        v = true;
        const parent = el.parentElement;
        if (parent && parent !== document.body && parent !== document.documentElement) {
            let regions = 0, hasVisible = false, hasHidden = false;
            for (const sib of parent.children) {
                if (structCount(sib) >= 2) {
                    regions++;
                    if (visibleCount(sib) > 0) hasVisible = true;
                    else hasHidden = true;
                }
            }
            if (regions >= 2 && hasVisible && hasHidden) {
                v = visibleCount(el) > 0;
            }
        }
        activeCache.set(el, v);
        return v;
    };
    const containerOf = (node) => {
        let p = node.parentElement;
        while (p && p !== document.body && p !== document.documentElement) {
            if (structCount(p) >= 2) {
                const parent = p.parentElement;
                if (parent && parent !== document.body && parent !== document.documentElement) {
                    let regions = 0, hasVisible = false, hasHidden = false;
                    for (const sib of parent.children) {
                        if (structCount(sib) >= 2) {
                            regions++;
                            if (visibleCount(sib) > 0) hasVisible = true;
                            else hasHidden = true;
                        }
                    }
                    if (regions >= 2 && hasVisible && hasHidden) return p;
                }
            }
            p = p.parentElement;
        }
        return null;
    };
    const countMatches = (sel) => {
        try { return document.querySelectorAll(sel).length; } catch (e) { return 0; }
    };
    const attrSelector = (attr, value) =>
        "[" + attr + "=" + JSON.stringify(value) + "]";
    const cssPath = (el) => {
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1) {
            const nodeTag = node.tagName.toLowerCase();
            const nodeType = (node.getAttribute("type") || "").toLowerCase();
            let part = (nodeTag === "input" && nodeType)
                ? nodeTag + "[type=" + JSON.stringify(nodeType) + "]" : nodeTag;
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
            if (countMatches(candidate) === 1) return candidate;
            if (parent === null || parent === document.documentElement) break;
            node = parent;
        }
        return parts.join(" > ") || el.tagName.toLowerCase();
    };
    const domPath = (el) => {
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1) {
            parts.unshift(node.tagName.toLowerCase());
            if (node === document.body) break;
            node = node.parentElement;
        }
        return parts.join(" > ");
    };
    const DATE_CTX_SEL = [
        ".picker", ".calendar", ".ant-picker", ".ant-calendar",
        ".el-date", ".el-date-picker", ".el-picker-panel",
        ".t-date-picker", "[class*='picker']", "[class*='calendar']",
        "[class*='date-picker']", "[class*='datepicker']"
    ].join(",");
    const NAV_RE = /上一|下一|上个月|下个月|prev|next|arrow|chevron|backward|forward/i;
    const MONTH_RE = /年|月|year|month|decade/i;
    const semanticTag = (el, tag, textVal) => {
        let ctx = null;
        try { ctx = el.closest(DATE_CTX_SEL); } catch (e) { ctx = null; }
        if (!ctx) return null;
        const hint = ((el.getAttribute("aria-label") || "") + " " +
                      (el.getAttribute("class") || "")).trim();
        if (NAV_RE.test(hint)) return "calendar-navigation";
        if ((tag === "td" || tag === "div" || tag === "span") &&
            /^\d{1,2}$/.test(textVal)) return "calendar-day";
        if (MONTH_RE.test(hint)) return "calendar-month";
        return null;
    };
    const nodes = Array.from(document.querySelectorAll(tagSel));
    const readText = (n) => (n.innerText || n.getAttribute("aria-label") || "")
        .replace(/\s+/g, " ").trim().slice(0, 120);
    const textCount = new Map();
    for (const n of nodes) {
        const t = readText(n);
        if (t) textCount.set(t, (textCount.get(t) || 0) + 1);
    }
    const selFor = (el, tag, textVal) => {
        for (const attr of ["data-testid", "data-test", "data-qa"]) {
            const v = el.getAttribute(attr);
            if (v) {
                const sel = attrSelector(attr, v);
                if (countMatches(sel) === 1) return sel;
            }
        }
        const type = (el.getAttribute("type") || "").toLowerCase();
        const base = (tag === "input" && type)
            ? tag + "[type=" + JSON.stringify(type) + "]" : tag;
        if (el.id) {
            const sel = "#" + CSS.escape(el.id);
            if (countMatches(sel) === 1) return sel;
        }
        const name = el.getAttribute("name");
        if (name) {
            const sel = base + "[name=" + JSON.stringify(name) + "]";
            if (countMatches(sel) === 1) return sel;
        }
        const aria = el.getAttribute("aria-label");
        if (aria) {
            const sel = base + "[aria-label=" + JSON.stringify(aria) + "]";
            if (countMatches(sel) === 1) return sel;
        }
        if (textVal && textCount.get(textVal) === 1) {
            return "text=" + JSON.stringify(textVal.slice(0, 60));
        }
        return cssPath(el);
    };
    const out = [];
    for (const n of nodes) {
        const tag = n.tagName.toLowerCase();
        if (tag === "input") {
            const t = (n.type || "text").toLowerCase();
            if (t === "hidden" || t === "submit" || t === "button" || t === "image") continue;
        }
        const style = getComputedStyle(n);
        const rect = n.getBoundingClientRect();
        const screened = style.display === "none" ||
                         style.visibility === "hidden" ||
                         rect.width <= 0 || rect.height <= 0;
        if (screened && scope !== "page") continue;
        let textVal = readText(n);
        if (filters.text) {
            if (!textVal || !textVal.toLowerCase().includes(filters.text.toLowerCase())) continue;
        }
        let roleAttr = n.getAttribute("role") || "";
        if (!roleAttr) {
            if (tag === "a") roleAttr = "link";
            else if (tag === "button") roleAttr = "button";
            else if (tag === "select") roleAttr = "combobox";
            else if (tag === "textarea") roleAttr = "textbox";
            else if (tag === "input") {
                const t = (n.type || "text").toLowerCase();
                roleAttr = (t === "checkbox" || t === "radio") ? t : "textbox";
            }
        }
        if (filters.role && roleAttr && !roleAttr.toLowerCase().includes(filters.role.toLowerCase())) continue;

        const selector = selFor(n, tag, textVal);

        const inViewport = rect.left < vw && rect.right > 0 &&
                           rect.top < vh && rect.bottom > 0;
        const pe = (style.pointerEvents || "auto").toLowerCase();
        const disabled = n.disabled === true ||
                         n.getAttribute("aria-disabled") === "true" ||
                         pe === "none";

        const container = containerOf(n);
        const inActive = container ? isActiveContainer(container) : true;
        if (scope === "visible" && !(inViewport && inActive)) continue;
        if (scope === "container" && !inActive) continue;

        let receivesEvents = true;
        if (inViewport && rect.width > 0 && rect.height > 0) {
            const hit = document.elementFromPoint(
                rect.left + rect.width / 2, rect.top + rect.height / 2);
            receivesEvents = !!hit && (hit === n || n.contains(hit));
        }

        out.push({
            tag: tag,
            text: textVal,
            role: roleAttr,
            id: n.id || "",
            value: tag === "input" ? (n.value || "") : "",
            ariaLabel: n.getAttribute("aria-label") || "",
            selector: selector,
            semantic: semanticTag(n, tag, textVal),
            path: domPath(n),
            enabled: !disabled,
            receivesEvents: receivesEvents,
            inViewport: inViewport,
            inActive: inActive,
            rect: {
                x: Math.round(rect.left), y: Math.round(rect.top),
                w: Math.round(rect.width), h: Math.round(rect.height)
            },
            visibility: {
                display: style.display, visibility: style.visibility,
                pointerEvents: pe
            },
        });
    }
    return out;
}
"""
