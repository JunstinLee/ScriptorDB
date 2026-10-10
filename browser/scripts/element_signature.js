
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
