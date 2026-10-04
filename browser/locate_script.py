from __future__ import annotations

# `browser.runtime.locate_elements` 第一段：一次 evaluate 完成布局初筛 + 信号抽取。
# 契约：这里只产出原始信号（selector / enabled / receivesEvents / inViewport /
# inActive / rect / visibility …），"可操作性三态"一律由 Python 侧的
# `_confirm_actionable` 判定，避免字段语义在两层之间漂移。
# 元素稳定签名（阶段 1 铸造 / 阶段 4 执行期复算共用同一份源码，避免两层语义漂移）。
# 只读属性派生信号：tag / role / aria-label / 归一化 text；刻意排除 value 与 rect ——
# value 随输入变化、rect 随布局变化，都会把「未变的元素」误判成 stale。
ELEMENT_SIGNATURE_JS = r"""
(el, tag, textVal) => {
    if (tag === undefined) tag = (el.tagName || "").toLowerCase();
    if (textVal === undefined) {
        textVal = el.getAttribute("aria-label") || el.textContent || "";
    }
    const role = (el.getAttribute("role") || "").trim();
    const aria = (el.getAttribute("aria-label") || "").trim();
    const text = (textVal || "").replace(/\s+/g, " ").trim().slice(0, 120);
    return [tag, role, aria, text].join("\u0001");
}
"""

LOCATE_ELEMENTS_JS = r"""
(filters) => {
    const signatureOf = __ELEMENT_SIGNATURE__;
    const tagSel = [
        "a", "button", "input", "select", "textarea",
        "li", "div", "span", "td", "label",
        "[role='button']", "[role='link']", "[role='tab']",
        "[role='menuitem']", "[role='checkbox']", "[role='radio']",
        "[role='textbox']", "[role='combobox']", "[role='searchbox']",
        "[role='switch']", "[role='option']"
    ].join(",");
    const scope = filters.scope || "visible";
    const extraSel = filters.extraSelector || "";
    const overlaySel = filters.overlaySelector || "";
    const quotas = filters.familyQuotas || {};
    const totalCap = filters.totalCap || 60;
    let classRe = null;
    try {
        classRe = filters.classPattern ? new RegExp(filters.classPattern, "i") : null;
    } catch (e) { classRe = null; }
    const interactiveAria = ["aria-haspopup", "aria-expanded", "aria-controls"];
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
    // 候选池 = 标准控件（tagSel）∪ 组件库可交互节点（extraSel）。
    // 只有非标准控件才过 extraInteractive 判定，标准控件保持原语义。
    const primarySet = new Set(document.querySelectorAll(tagSel));
    const nodes = Array.from(primarySet);
    if (extraSel) {
        for (const el of document.querySelectorAll(extraSel)) {
            if (!primarySet.has(el)) nodes.push(el);
        }
    }
    const INTERACTIVE_TAGS = new Set([
        "div", "span", "td", "th", "li", "tr", "a", "label", "i", "em", "b",
        "strong", "p", "button", "input", "select", "textarea", "option",
        "summary", "section",
    ]);
    const extraInteractive = (el, tag) => {
        if (!INTERACTIVE_TAGS.has(tag)) return false;
        for (const attr of interactiveAria) {
            if (el.hasAttribute(attr)) return true;
        }
        if ((el.getAttribute("role") || "").trim()) return true;
        const tabindex = el.getAttribute("tabindex");
        if (tabindex !== null && Number(tabindex) >= 0) return true;
        if (classRe && classRe.test(el.getAttribute("class") || "")) return true;
        const dataset = el.dataset || {};
        for (const key in dataset) {
            if (/click|action|toggle|open|trigger|select/.test(key)) return true;
        }
        return false;
    };
    // 候选族：只为「防止单一大族垄断名额」，不追求精确识别控件类型。
    // 全部基于 tag / class / role / text 的属性读取，不触碰布局。
    const DATE_TOKENS = /date|calendar|picker|month|year|day/i;
    const familyOf = (el, tag, roleAttr, textVal) => {
        if (semanticTag(el, tag, textVal) === "calendar-navigation") return "nav";
        let n = el, depth = 0;
        while (n && depth <= 4) {
            const cls = n.getAttribute("class") || "";
            if (cls && DATE_TOKENS.test(cls)) return "date";
            n = n.parentElement;
            depth++;
        }
        if (tag === "input" || tag === "select" || tag === "textarea") return "input";
        if (/textbox|combobox|searchbox|switch|checkbox|radio|spinbutton/.test(roleAttr)) {
            return "input";
        }
        const navHint = (el.getAttribute("aria-label") || "") + " " +
                        (el.getAttribute("class") || "") + " " + textVal;
        if (NAV_RE.test(navHint)) return "nav";
        if (tag === "button" || tag === "summary" ||
            /^(button|menuitem|option|tab|switch)$/.test(roleAttr)) return "button";
        if (tag === "a" || roleAttr === "link") return "link";
        return "other";
    };
    // 族内轻量评分：稳定属性优先，不涉及任何布局属性。
    const cheapScore = (el, tag, family, textVal) => {
        let score = 0;
        if (el.id) score += 3;
        for (const attr of ["data-testid", "data-test", "data-qa"]) {
            if (el.getAttribute(attr)) { score += 3; break; }
        }
        if (el.getAttribute("aria-label")) score += 2;
        for (const attr of interactiveAria) {
            if (el.hasAttribute(attr)) { score += 1; break; }
        }
        if (el.getAttribute("role")) score += 1;
        if (classRe && classRe.test(el.getAttribute("class") || "")) score += 2;
        if (family === "date") score += 2;
        if (semanticTag(el, tag, textVal) === "calendar-day") score += 3;
        if (tag === "button" || tag === "a" || tag === "input" || tag === "select") score += 1;
        if (textVal && textVal.length <= 40) score += 1;
        return score;
    };
    const overlayCache = new WeakMap();
    const overlayOf = (el) => {
        let owner = overlayCache.get(el);
        if (owner !== undefined) return owner;
        owner = null;
        if (overlaySel) {
            let n = el;
            while (n && n.nodeType === 1 && n !== document.documentElement) {
                try {
                    if (n.matches && n.matches(overlaySel) && laidOut(n)) {
                        owner = n;
                        break;
                    }
                } catch (e) { /* 非法/不支持的选择器：忽略该节点 */ }
                n = n.parentElement;
            }
        }
        overlayCache.set(el, owner);
        return owner;
    };
    const keyCache = new WeakMap();
    const containerKeyOf = (el) => {
        let key = keyCache.get(el);
        if (key !== undefined) return key;
        key = el.id ? "#" + el.id : domPath(el);
        keyCache.set(el, key);
        return key;
    };
    const readText = (n) => (n.innerText || n.getAttribute("aria-label") || "")
        .replace(/\s+/g, " ").trim().slice(0, 120);
    // 签名专用文本：只由属性 / 非渲染文本派生，且与 ELEMENT_SIGNATURE_JS 的缺省
    // 来源同序同源（aria-label → textContent），避免 innerText 的渲染抖动污染签名。
    const sigText = (n) => n.getAttribute("aria-label") || n.textContent || "";
    const textCount = new Map();
    for (const n of nodes) {
        const t = readText(n);
        if (t) textCount.set(t, (textCount.get(t) || 0) + 1);
    }
    const selFor = (el, tag, textVal) => {
        const dateContext = el.closest(DATE_CTX_SEL);
        const contextSelector = dateContext ? cssPath(dateContext) : "";
        const stableAttrs = ["data-testid", "data-test", "data-qa"];
        if (dateContext) stableAttrs.push("data-date", "data-value", "data-day", "title");
        for (const attr of stableAttrs) {
            const v = el.getAttribute(attr);
            if (v) {
                const local = attrSelector(attr, v);
                const scoped = contextSelector ? contextSelector + " " + local : local;
                if (countMatches(scoped) === 1) return scoped;
                if (countMatches(local) === 1) return local;
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
    // 第一段：低成本候选族判断 + 族内评分。只读属性，不做任何布局查询，
    // 因此可以对整个 DOM 跑而不触发重排。
    const candidates = [];
    for (const n of nodes) {
        const tag = n.tagName.toLowerCase();
        if (tag === "input") {
            const t = (n.type || "text").toLowerCase();
            if (t === "hidden" || t === "submit" || t === "button" || t === "image") continue;
        }
        if (!primarySet.has(n) && !extraInteractive(n, tag)) continue;
        const textVal = readText(n);
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
        const family = familyOf(n, tag, roleAttr, textVal);
        candidates.push({
            node: n, tag: tag, roleAttr: roleAttr, text: textVal, family: family,
            score: cheapScore(n, tag, family, textVal),
        });
    }

    // 第二段：族配额 + 共享余量 → 硬上限。这里就截断，后面昂贵的布局检查
    // 只会看到 ≤ totalCap 个节点。
    const FAMILIES = ["date", "nav", "input", "button", "link", "other"];
    const buckets = {};
    for (const f of FAMILIES) buckets[f] = [];
    for (const c of candidates) {
        (buckets[c.family] || buckets.other).push(c);
    }
    for (const f of FAMILIES) buckets[f].sort((a, b) => b.score - a.score);
    const admitted = [];
    const cursor = {};
    for (const f of FAMILIES) cursor[f] = 0;
    const takeUpTo = (f, limit) => {
        let taken = 0;
        while (cursor[f] < buckets[f].length && taken < limit &&
               admitted.length < totalCap) {
            admitted.push(buckets[f][cursor[f]++]);
            taken++;
        }
    };
    // 各族先拿保底配额；配额用完就不再收同族元素。
    for (const f of FAMILIES) takeUpTo(f, quotas[f] || 0);
    // 剩余名额按族轮转，避免单一大族垄断共享余量。
    let progress = true;
    while (admitted.length < totalCap && progress) {
        progress = false;
        for (const f of FAMILIES) {
            if (admitted.length >= totalCap) break;
            const before = admitted.length;
            takeUpTo(f, 1);
            if (admitted.length > before) progress = true;
        }
    }

    // 第三段：只对受控候选做布局初筛（可见性 / 视口 / 命中测试）。
    const out = [];
    for (const c of admitted) {
        const n = c.node;
        const tag = c.tag;
        const roleAttr = c.roleAttr;
        const textVal = c.text;
        const style = getComputedStyle(n);
        const rect = n.getBoundingClientRect();
        const screened = style.display === "none" ||
                         style.visibility === "hidden" ||
                         rect.width <= 0 || rect.height <= 0;
        if (screened && scope !== "page") continue;

        const selector = selFor(n, tag, textVal);

        const inViewport = rect.left < vw && rect.right > 0 &&
                           rect.top < vh && rect.bottom > 0;
        const pe = (style.pointerEvents || "auto").toLowerCase();
        const disabled = n.disabled === true ||
                         n.getAttribute("aria-disabled") === "true" ||
                         pe === "none";

        const overlayEl = overlayOf(n);
        const container = containerOf(n);
        const owner = overlayEl || container;
        const containerKey = owner ? containerKeyOf(owner) : "";
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
            signature: signatureOf(n, tag, sigText(n)),
            semantic: semanticTag(n, tag, textVal),
            path: domPath(n),
            enabled: !disabled,
            receivesEvents: receivesEvents,
            inViewport: inViewport,
            inActive: inActive,
            overlay: !!overlayEl,
            containerKey: containerKey,
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
""".replace("__ELEMENT_SIGNATURE__", ELEMENT_SIGNATURE_JS)
