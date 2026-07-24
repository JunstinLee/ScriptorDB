#!/usr/bin/env python3
"""
分层布局诊断工具。

用法:
    uv run python scripts//layout_diagnostic.py <url> [选项]

示例:
    uv run python scripts/layout_diagnostic.py http://localhost:5173 --duration 30 --interval 200
    uv run python scripts/layout_diagnostic.py https://example.com --output ./my-report

依赖: playwright (pip install playwright && playwright install chromium)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("需要安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class WindowSnapshot:
    """第一层：浏览器窗口信息"""
    timestamp: float = 0.0
    inner_width: int = 0
    inner_height: int = 0
    outer_width: int = 0
    outer_height: int = 0
    device_pixel_ratio: float = 1.0
    visual_viewport_width: int = 0
    visual_viewport_height: int = 0


@dataclass
class PageLayoutSnapshot:
    """第二层：页面布局信息"""
    timestamp: float = 0.0
    doc_client_width: int = 0
    doc_scroll_width: int = 0
    body_client_width: int = 0
    body_scroll_width: int = 0
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    has_horizontal_scrollbar: bool = False


@dataclass
class ElementInfo:
    """第三层：单个元素信息"""
    tag: str = ""
    width: float = 0.0
    scroll_width: float = 0.0
    client_width: float = 0.0
    class_name: str = ""
    element_id: str = ""
    css_selector: str = ""
    xpath: str = ""
    text_preview: str = ""


@dataclass
class WidestElementsSnapshot:
    """第三层：最宽元素快照"""
    timestamp: float = 0.0
    elements: list[ElementInfo] = field(default_factory=list)


@dataclass
class MutationRecord:
    """第四层：变化记录"""
    timestamp: float = 0.0
    event_type: str = ""          # resize_observer / mutation / scroll / resize / cls
    target_selector: str = ""
    attribute_name: str = ""
    old_value: str = ""
    new_value: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JS 注入脚本
# ---------------------------------------------------------------------------

COLLECT_WINDOW_INFO = """() => {
    return {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        outerWidth: window.outerWidth,
        outerHeight: window.outerHeight,
        devicePixelRatio: window.devicePixelRatio,
        visualViewportWidth: window.visualViewport?.width ?? 0,
        visualViewportHeight: window.visualViewport?.height ?? 0,
    };
}"""

COLLECT_PAGE_LAYOUT = """() => {
    const doc = document.documentElement;
    const body = document.body;
    return {
        docClientWidth: doc.clientWidth,
        docScrollWidth: doc.scrollWidth,
        bodyClientWidth: body ? body.clientWidth : 0,
        bodyScrollWidth: body ? body.scrollWidth : 0,
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        hasHorizontalScrollbar: doc.scrollWidth > doc.clientWidth,
    };
}"""

COLLECT_WIDEST_ELEMENTS = """(topN) => {
    const all = document.querySelectorAll('*');
    const results = [];
    for (const el of all) {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0) continue;
        const tag = el.tagName.toLowerCase();
        const cls = (el.className && typeof el.className === 'string')
            ? el.className.trim().split(/\\s+/).slice(0, 5).join(' ')
            : '';
        const id = el.id || '';
        results.push({
            tag: tag,
            width: rect.width,
            scrollWidth: el.scrollWidth ?? rect.width,
            clientWidth: el.clientWidth ?? rect.width,
            className: cls,
            elementId: id,
            cssSelector: id ? '#' + id : (cls ? tag + '.' + cls.split(' ').join('.') : tag),
            xpath: '',
            textPreview: (el.textContent || '').trim().slice(0, 40),
        });
    }
    results.sort((a, b) => b.width - a.width);
    return results.slice(0, topN);
}"""

INJECT_OBSERVERS = """
window.__layoutDiag = {
    mutations: [],
    resizes: [],
    scrolls: [],
    sizeCache: {},
    enabled: true,
};

function _selector(el) {
    if (!el || el === document) return 'document';
    if (el === document.documentElement) return 'html';
    if (el === document.body) return 'body';
    if (el.id) return '#' + el.id;
    const cls = (el.className && typeof el.className === 'string')
        ? el.className.trim().split(/\\s+/).slice(0, 3).join('.')
        : '';
    const tag = el.tagName.toLowerCase();
    return cls ? tag + '.' + cls : tag;
}

function _recordMutation(type, target, attr, oldVal, newVal) {
    window.__layoutDiag.mutations.push({
        t: performance.now(),
        eventType: type,
        targetSelector: _selector(target),
        attributeName: attr || '',
        oldValue: String(oldVal || ''),
        newValue: String(newVal || ''),
        details: {},
    });
}

// ResizeObserver
const ro = new ResizeObserver((entries) => {
    for (const entry of entries) {
        const sel = _selector(entry.target);
        const cr = entry.contentRect;
        const key = sel + ':resize';
        const prev = window.__layoutDiag.sizeCache[key];
        const w = Math.round(cr.width);
        const h = Math.round(cr.height);
        if (prev && (prev.w !== w || prev.h !== h)) {
            _recordMutation('resize_observer', entry.target, 'size',
                prev.w + 'x' + prev.h, w + 'x' + h);
        }
        window.__layoutDiag.sizeCache[key] = { w, h };
    }
});
ro.observe(document.documentElement);
ro.observe(document.body);

// MutationObserver
const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
        if (m.type === 'attributes') {
            const oldVal = m.oldValue || '';
            const newVal = m.target.getAttribute ? (m.target.getAttribute(m.attributeName) || '') : '';
            if (oldVal !== newVal) {
                _recordMutation('mutation_attribute', m.target, m.attributeName, oldVal, newVal);
            }
        } else if (m.type === 'childList') {
            const added = m.addedNodes.length;
            const removed = m.removedNodes.length;
            if (added > 0 || removed > 0) {
                _recordMutation('mutation_childlist', m.target, '',
                    '', `added=${added}, removed=${removed}`);
            }
        }
    }
});
mo.observe(document.documentElement, {
    attributes: true,
    attributeOldValue: true,
    childList: true,
    subtree: true,
});

// PerformanceObserver (Layout Shift)
if (typeof PerformanceObserver !== 'undefined') {
    try {
        const po = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                window.__layoutDiag.mutations.push({
                    t: performance.now(),
                    eventType: 'layout_shift',
                    targetSelector: '',
                    attributeName: '',
                    oldValue: '',
                    newValue: String(entry.value),
                    details: { sources: entry.sources?.map(s => ({ node: s.node ? _selector(s.node) : '', currentRect: s.currentRect })) || [] },
                });
            }
        });
        po.observe({ type: 'layout-shift', buffered: true });
    } catch (e) {}
}

// Scroll events
window.addEventListener('scroll', () => {
    window.__layoutDiag.scrolls.push({ t: performance.now(), x: window.scrollX, y: window.scrollY });
}, { passive: true });

// Resize events
window.addEventListener('resize', () => {
    _recordMutation('window_resize', window, '', '',
        window.innerWidth + 'x' + window.innerHeight);
});
"""

FLUSH_OBSERVER_BUFFERS = """() => {
    const diag = window.__layoutDiag;
    if (!diag) return { mutations: [], resizes: [], scrollCount: 0 };
    const out = {
        mutations: diag.mutations.splice(0),
        sizeCache: diag.sizeCache ? JSON.parse(JSON.stringify(diag.sizeCache)) : {},
        scrollCount: diag.scrolls.length,
    };
    diag.scrolls = [];
    return out;
}"""

# ---------------------------------------------------------------------------
# 诊断引擎
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticConfig:
    url: str = ""
    duration: int = 30
    interval_ms: int = 200
    top_n: int = 20
    output_dir: str = ""
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720


class LayoutDiagnostic:
    def __init__(self, config: DiagnosticConfig):
        self.config = config
        self.start_time = 0.0

        # Layer 1 & 2 时间线
        self.window_timeline: list[WindowSnapshot] = []
        self.page_timeline: list[PageLayoutSnapshot] = []

        # Layer 3 最宽元素
        self.widest_snapshots: list[WidestElementsSnapshot] = []

        # Layer 4 变化事件
        self.mutation_log: list[MutationRecord] = []

        # 尺寸变化追踪器 (选择器 -> 宽度时间线)
        self.size_changes: dict[str, list[tuple[float, float]]] = {}

        self._output_path = Path(config.output_dir)
        self._screenshots_dir = self._output_path / "screenshots"

    # ------------------------------------------------------------------
    # 采集方法
    # ------------------------------------------------------------------

    def _collect_window(self, page) -> WindowSnapshot:
        info = page.evaluate(COLLECT_WINDOW_INFO)
        snap = WindowSnapshot(
            timestamp=time.time(),
            inner_width=info.get("innerWidth", 0),
            inner_height=info.get("innerHeight", 0),
            outer_width=info.get("outerWidth", 0),
            outer_height=info.get("outerHeight", 0),
            device_pixel_ratio=info.get("devicePixelRatio", 1.0),
            visual_viewport_width=info.get("visualViewportWidth", 0),
            visual_viewport_height=info.get("visualViewportHeight", 0),
        )
        self.window_timeline.append(snap)
        return snap

    def _collect_page_layout(self, page) -> PageLayoutSnapshot:
        info = page.evaluate(COLLECT_PAGE_LAYOUT)
        snap = PageLayoutSnapshot(
            timestamp=time.time(),
            doc_client_width=info.get("docClientWidth", 0),
            doc_scroll_width=info.get("docScrollWidth", 0),
            body_client_width=info.get("bodyClientWidth", 0),
            body_scroll_width=info.get("bodyScrollWidth", 0),
            scroll_x=info.get("scrollX", 0.0),
            scroll_y=info.get("scrollY", 0.0),
            has_horizontal_scrollbar=info.get("hasHorizontalScrollbar", False),
        )
        self.page_timeline.append(snap)
        return snap

    def _collect_widest_elements(self, page) -> WidestElementsSnapshot:
        raw = page.evaluate(COLLECT_WIDEST_ELEMENTS, self.config.top_n)
        elements = [
            ElementInfo(
                tag=e.get("tag", ""),
                width=e.get("width", 0.0),
                scroll_width=e.get("scrollWidth", 0.0),
                client_width=e.get("clientWidth", 0.0),
                class_name=e.get("className", ""),
                element_id=e.get("elementId", ""),
                css_selector=e.get("cssSelector", ""),
                xpath=e.get("xpath", ""),
                text_preview=e.get("textPreview", ""),
            )
            for e in raw
        ]
        snap = WidestElementsSnapshot(timestamp=time.time(), elements=elements)
        self.widest_snapshots.append(snap)
        return snap

    def _flush_observers(self, page) -> dict[str, Any]:
        return page.evaluate(FLUSH_OBSERVER_BUFFERS)

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.config.headless)
            context = browser.new_context(
                viewport={"width": self.config.viewport_width, "height": self.config.viewport_height}
            )
            page = context.new_page()

            # 输出目录
            self._output_path.mkdir(parents=True, exist_ok=True)
            self._screenshots_dir.mkdir(parents=True, exist_ok=True)

            # 打开页面
            page.goto(self.config.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # 注入监听器
            page.evaluate(INJECT_OBSERVERS)

            # 初始化尺寸缓存
            init_wide = page.evaluate(COLLECT_WIDEST_ELEMENTS, self.config.top_n)
            for e in init_wide:
                sel = e.get("cssSelector", "") or e.get("tag", "")
                self.size_changes[sel] = [(0.0, e.get("width", 0.0))]

            # 拍摄起始截图
            start_screenshot = str(self._screenshots_dir / "start.png")
            page.screenshot(path=start_screenshot, full_page=True)

            self.start_time = time.time()
            deadline = self.start_time + self.config.duration
            last_flush = self.start_time

            while time.time() < deadline:
                loop_start = time.time()

                # Layer 1: 窗口信息
                self._collect_window(page)

                # Layer 2: 页面布局
                layout = self._collect_page_layout(page)

                # Layer 3: 最宽元素（每 1 秒采集一次完整列表）
                if (loop_start - self.start_time) % 1.0 < self.config.interval_ms / 1000 * 2:
                    wide = self._collect_widest_elements(page)
                    for e in wide.elements:
                        sel = e.css_selector or e.tag
                        if sel not in self.size_changes:
                            self.size_changes[sel] = []
                        prev_width = self.size_changes[sel][-1][1] if self.size_changes[sel] else 0
                        if abs(e.width - prev_width) > 0.5:
                            self.size_changes[sel].append((loop_start - self.start_time, e.width))

                # Layer 4: 刷新观察者缓冲区
                if loop_start - last_flush >= 0.5:
                    buf = self._flush_observers(page)
                    for m in buf.get("mutations", []):
                        self.mutation_log.append(MutationRecord(
                            timestamp=time.time(),
                            event_type=m.get("eventType", ""),
                            target_selector=m.get("targetSelector", ""),
                            attribute_name=m.get("attributeName", ""),
                            old_value=m.get("oldValue", ""),
                            new_value=m.get("newValue", ""),
                            details=m.get("details", {}),
                        ))
                    last_flush = loop_start

                elapsed = time.time() - loop_start
                sleep_ms = max(0, self.config.interval_ms / 1000 - elapsed)
                time.sleep(sleep_ms)

            # 拍摄结束截图
            end_screenshot = str(self._screenshots_dir / "end.png")
            page.screenshot(path=end_screenshot, full_page=True)

            # 最后一次刷新
            buf = self._flush_observers(page)
            for m in buf.get("mutations", []):
                self.mutation_log.append(MutationRecord(
                    timestamp=time.time(),
                    event_type=m.get("eventType", ""),
                    target_selector=m.get("targetSelector", ""),
                    attribute_name=m.get("attributeName", ""),
                    old_value=m.get("oldValue", ""),
                    new_value=m.get("newValue", ""),
                    details=m.get("details", {}),
                ))

            browser.close()

        return self._generate_report()

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    def _generate_report(self) -> dict[str, Any]:
        total_duration = time.time() - self.start_time

        # 汇总信息
        first_window = self.window_timeline[0] if self.window_timeline else None
        last_window = self.window_timeline[-1] if self.window_timeline else None
        first_page = self.page_timeline[0] if self.page_timeline else None
        last_page = self.page_timeline[-1] if self.page_timeline else None

        window_changed = False
        if first_window and last_window:
            window_changed = (
                first_window.inner_width != last_window.inner_width
                or first_window.outer_width != last_window.outer_width
            )

        page_expanded = False
        max_scroll_width = 0
        if self.page_timeline:
            max_scroll_width = max(p.doc_scroll_width for p in self.page_timeline)
            page_expanded = max_scroll_width > (last_page.doc_client_width if last_page else self.config.viewport_width)

        report = {
            "url": self.config.url,
            "diagnostic_duration_s": round(total_duration, 2),
            "interval_ms": self.config.interval_ms,
            "viewport": {
                "configured": f"{self.config.viewport_width}x{self.config.viewport_height}",
                "initial_inner": (
                    f"{first_window.inner_width}x{first_window.inner_height}" if first_window else "N/A"
                ),
                "final_inner": (
                    f"{last_window.inner_width}x{last_window.inner_height}" if last_window else "N/A"
                ),
                "window_changed": window_changed,
            },
            "page_layout": {
                "initial_doc_client_width": first_page.doc_client_width if first_page else 0,
                "initial_doc_scroll_width": first_page.doc_scroll_width if first_page else 0,
                "final_doc_client_width": last_page.doc_client_width if last_page else 0,
                "final_doc_scroll_width": last_page.doc_scroll_width if last_page else 0,
                "max_scroll_width": max_scroll_width,
                "page_expanded_during_diagnostic": page_expanded,
                "horizontal_scrollbar_appeared": any(
                    p.has_horizontal_scrollbar for p in self.page_timeline
                ),
            },
            "screenshots": {
                "start": str(self._screenshots_dir / "start.png"),
                "end": str(self._screenshots_dir / "end.png"),
            },
            "total_mutations": len(self.mutation_log),
            "total_resize_events": sum(
                1 for m in self.mutation_log if m.event_type in ("resize_observer", "window_resize")
            ),
            "total_layout_shifts": sum(
                1 for m in self.mutation_log if m.event_type == "layout_shift"
            ),
            "elements_tracked": len(self.size_changes),
            "elements_that_changed": sum(
                1 for v in self.size_changes.values() if len(v) > 1
            ),
        }

        # 写入 layout-report.json
        report_path = self._output_path / "layout-report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        # 写入 timeline.json
        timeline = {
            "window": [
                {
                    "t": round(s.timestamp - self.start_time, 3),
                    "innerWidth": s.inner_width,
                    "innerHeight": s.inner_height,
                    "outerWidth": s.outer_width,
                    "outerHeight": s.outer_height,
                    "devicePixelRatio": s.device_pixel_ratio,
                    "visualViewportWidth": s.visual_viewport_width,
                    "visualViewportHeight": s.visual_viewport_height,
                }
                for s in self.window_timeline
            ],
            "page": [
                {
                    "t": round(s.timestamp - self.start_time, 3),
                    "docClientWidth": s.doc_client_width,
                    "docScrollWidth": s.doc_scroll_width,
                    "bodyClientWidth": s.body_client_width,
                    "bodyScrollWidth": s.body_scroll_width,
                    "scrollX": s.scroll_x,
                    "scrollY": s.scroll_y,
                    "hasHorizontalScrollbar": s.has_horizontal_scrollbar,
                }
                for s in self.page_timeline
            ],
        }
        (self._output_path / "timeline.json").write_text(
            json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 写入 largest-elements.json
        largest = [
            {
                "t": round(s.timestamp - self.start_time, 3),
                "elements": [
                    {
                        "tag": e.tag,
                        "width": e.width,
                        "scrollWidth": e.scroll_width,
                        "clientWidth": e.client_width,
                        "cssSelector": e.css_selector,
                        "className": e.class_name,
                        "id": e.element_id,
                        "textPreview": e.text_preview,
                    }
                    for e in s.elements[:10]
                ],
            }
            for s in self.widest_snapshots
        ]
        (self._output_path / "largest-elements.json").write_text(
            json.dumps(largest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 写入 mutations.json
        mutations = [
            {
                "t": round(m.timestamp - self.start_time, 3),
                "eventType": m.event_type,
                "targetSelector": m.target_selector,
                "attributeName": m.attribute_name,
                "oldValue": m.old_value,
                "newValue": m.new_value,
                "details": m.details,
            }
            for m in self.mutation_log
        ]
        (self._output_path / "mutations.json").write_text(
            json.dumps(mutations, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 写入 resize-events.json
        resize_events = [
            m for m in mutations
            if m["eventType"] in ("resize_observer", "window_resize")
        ]
        (self._output_path / "resize-events.json").write_text(
            json.dumps(resize_events, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 写入 performance.json
        perf_events = [
            m for m in mutations
            if m["eventType"] == "layout_shift"
        ]
        (self._output_path / "performance.json").write_text(
            json.dumps(perf_events, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return report

    # ------------------------------------------------------------------
    # 打印摘要
    # ------------------------------------------------------------------

    def print_summary(self, report: dict[str, Any]) -> None:
        print(f"\n{'=' * 60}")
        print("  Layout Diagnostic Report")
        print(f"{'=' * 60}")
        print(f"  URL:                     {report['url']}")
        print(f"  Duration:               {report['diagnostic_duration_s']}s")
        print(f"  Sampling interval:      {report['interval_ms']}ms")
        print(f"  Viewport:               {report['viewport']['configured']}")
        print()

        pl = report["page_layout"]
        print(f"  Initial doc scrollWidth:  {pl['initial_doc_scroll_width']}")
        print(f"  Final doc scrollWidth:    {pl['final_doc_scroll_width']}")
        print(f"  Max doc scrollWidth:      {pl['max_scroll_width']}")
        print(f"  Page expanded:            {pl['page_expanded_during_diagnostic']}")
        print(f"  Window changed:           {report['viewport']['window_changed']}")
        print()

        print(f"  Total mutations:          {report['total_mutations']}")
        print(f"  Resize events:            {report['total_resize_events']}")
        print(f"  Layout shifts:            {report['total_layout_shifts']}")
        print(f"  Elements tracked:         {report['elements_tracked']}")
        print(f"  Elements that changed:    {report['elements_that_changed']}")
        print()

        # 打印宽度变化最大的元素
        if self.size_changes:
            print("  Top size-changed elements:")
            changed = [
                (sel, vals)
                for sel, vals in self.size_changes.items()
                if len(vals) > 1
            ]
            changed.sort(key=lambda x: max(abs(a - b) for (_, a), (_, b) in zip(x[1], x[1][1:])), reverse=True)
            for sel, vals in changed[:10]:
                widths = [str(int(v[1])) for v in vals[:5]]
                print(f"    {sel:40s}  {' → '.join(widths)}")

        print()
        print(f"  Output directory:  {self._output_path}")
        print(f"  Files:")
        for name in sorted(os.listdir(self._output_path)):
            print(f"    {name}/" if os.path.isdir(self._output_path / name) else f"    {name}")
        print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="分层布局诊断工具 — 检测页面布局异常、元素溢出和尺寸漂移",
    )
    parser.add_argument("url", help="目标页面 URL")
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="诊断持续时间（秒），默认 30",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=200,
        help="采集间隔（毫秒），默认 200",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出目录，默认 scripts/layout_report_<timestamp>",
    )
    parser.add_argument(
        "--top-n", "-n",
        type=int,
        default=20,
        help="每轮采集的最宽元素数量，默认 20",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="显示浏览器窗口（非 headless）",
    )
    parser.add_argument(
        "--viewport-width", type=int, default=1280, help="初始视口宽度，默认 1280"
    )
    parser.add_argument(
        "--viewport-height", type=int, default=720, help="初始视口高度，默认 720"
    )

    args = parser.parse_args()

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = str(Path(__file__).resolve().parent / f"layout_report_{ts}")

    config = DiagnosticConfig(
        url=args.url,
        duration=args.duration,
        interval_ms=args.interval,
        top_n=args.top_n,
        output_dir=args.output,
        headless=not args.headed,
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height,
    )

    diag = LayoutDiagnostic(config)
    report = diag.run()
    diag.print_summary(report)

    return report


if __name__ == "__main__":
    main()
