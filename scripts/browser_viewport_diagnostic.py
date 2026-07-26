#!/usr/bin/env python3
"""
Browser Viewport Diagnostic Tool — 诊断 BrowserViewport 为何显示占位符而非截图。

用法:
    uv run python scripts/browser_viewport_diagnostic.py              # Layer 0-4（纯 API）
    uv run python scripts/browser_viewport_diagnostic.py --visual     # + Layer 5 Playwright 前端捕获
    uv run python scripts/browser_viewport_diagnostic.py --visual --trigger  # + 通过前端聊天框触发截图

要求:
    - 后端运行在 localhost:8000 (npm run dev:api)
    - 前端运行在 localhost:5173 (仅 --visual, npm run dev:web)
    - Playwright 已安装 (仅 --visual: pip install playwright && playwright install chromium)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
PLAYWRIGHT_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright  # noqa: F401

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# ANSI
# ---------------------------------------------------------------------------

_G = "\033[92m"
_R = "\033[91m"
_Y = "\033[93m"
_C = "\033[96m"
_B = "\033[1m"
_N = "\033[0m"

OK = _G + "PASS" + _N
FAIL = _R + "FAIL" + _N
SKIP = _Y + "SKIP" + _N
WARN = _Y + "WARN" + _N


def _tag(ok_: bool) -> str:
    return OK if ok_ else FAIL


def _icon(ok_: bool) -> str:
    return _G + "✔" + _N if ok_ else _R + "✘" + _N


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class LayerResult:
    layer: int
    title: str
    ok: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False


@dataclass
class Report:
    timestamp: str = ""
    layers: list[LayerResult] = field(default_factory=list)
    all_ok: bool = True
    root_cause: str = ""
    workspace_path: str = ""


# ---------------------------------------------------------------------------
# Diagnostic engine
# ---------------------------------------------------------------------------


class BrowserViewportDiagnostic:
    def __init__(self, *, visual: bool = False, trigger: bool = False, timeout: int = 10):
        self._visual = visual
        self._trigger = trigger and visual
        self._timeout = timeout
        self._results: list[LayerResult] = []
        self._workspace_path: Path | None = None
        self._browser_state: dict[str, Any] = {}
        self._output_dir = Path(__file__).resolve().parent
        self._screenshots_dir = self._output_dir / "screenshots"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, client: httpx.Client, path: str) -> httpx.Response | None:
        try:
            return client.get(f"{BACKEND_URL}{path}", timeout=self._timeout)
        except Exception:
            return None

    def _post(self, client: httpx.Client, path: str, body: dict) -> httpx.Response | None:
        try:
            return client.post(f"{BACKEND_URL}{path}", json=body, timeout=self._timeout)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Layer 0 — Backend reachable + workspace active
    # ------------------------------------------------------------------

    def _check_connectivity(self, client: httpx.Client) -> None:
        resp = self._get(client, "/api/browser/state")
        if resp is None:
            self._results.append(
                LayerResult(
                    layer=0,
                    title="Backend Connectivity",
                    ok=False,
                    message=f"Cannot reach {BACKEND_URL}. Is the backend running?\n        Start it with: npm run dev:api",
                )
            )
            return

        if resp.status_code == 409:
            self._results.append(
                LayerResult(
                    layer=0,
                    title="Workspace Active",
                    ok=False,
                    message="HTTP 409 — No active workspace.\n        Switch: uv run python main.py workspace switch <id>",
                )
            )
            return

        if resp.status_code != 200:
            self._results.append(
                LayerResult(
                    layer=0,
                    title="Backend Health",
                    ok=False,
                    message=f"Unexpected HTTP {resp.status_code}",
                )
            )
            return

        state = resp.json()
        self._browser_state = state

        self._results.append(
            LayerResult(
                layer=0,
                title="Backend Reachable",
                ok=True,
                message=f"{BACKEND_URL} → HTTP 200, browser_enabled active",
                data=state,
            )
        )

    # ------------------------------------------------------------------
    # Layer 1 — Browser launch state
    # ------------------------------------------------------------------

    def _check_browser_launch(self) -> None:
        state = self._browser_state
        launched = state.get("launched", False)
        url = state.get("url")
        title = state.get("title") or ""

        if not launched:
            self._results.append(
                LayerResult(
                    layer=1,
                    title="Browser Launched",
                    ok=True,
        message=(
            "Browser is NOT launched yet.\n"
            "        The LLM agent needs to call browser_launch first.\n"
            "        BrowserViewport currently shows: Monitor placeholder (等待智能体启动浏览器...)"
        ),
                    data={"launched": False},
                )
            )
            return

        if not url:
            self._results.append(
                LayerResult(
                    layer=1,
                    title="Browser Launched",
                    ok=True,
        message=(
            "Browser launched, but no page loaded (URL is empty).\n"
            "        The agent needs to call browser_navigate to load a page.\n"
            "        BrowserViewport currently shows: Loading spinner (浏览器启动中...)"
        ),
                    data={"launched": True, "url": None},
                )
            )
            return

        self._results.append(
            LayerResult(
                layer=1,
                title="Browser Launched + Page Loaded",
                ok=True,
                message=f"launched=True, url={url}, title={title[:60] or '(empty)'}",
                data={"launched": True, "url": url, "title": title},
            )
        )

    # ------------------------------------------------------------------
    # Layer 2 — Screenshot available in state
    # ------------------------------------------------------------------

    def _check_screenshot_available(self) -> None:
        state = self._browser_state
        if not state.get("launched") or not state.get("url"):
            self._results.append(
                LayerResult(
                    layer=2,
                    title="Screenshot Available (State)",
                    ok=True,
                    message="Prerequisite not met — browser must be launched with a loaded page.",
                    skipped=True,
                )
            )
            return

        avail: bool = state.get("screenshot_available", False)
        path: str | None = state.get("screenshot_path")
        actions: list[dict] = state.get("actions", [])

        if avail:
            self._results.append(
                LayerResult(
                    layer=2,
                    title="Screenshot Available (State)",
                    ok=True,
                    message=f"screenshot_available=True, path={path}",
                    data={"screenshot_path": path},
                )
            )
            return

        reason: str
        if path:
            reason = "TTL expired"
            msg = (
                f"Screenshot was taken (path={path}) but TTL expired (>30 s after capture).\n"
                "        ImageIcon placeholder is showing because the screenshot timed out.\n"
                "        Ask the agent to take a NEW screenshot."
            )
        else:
            has_action = any(a.get("tool") == "screenshot" for a in actions)
            if has_action:
                reason = "tool_failed"
                msg = (
                    "browser_screenshot was called but likely FAILED.\n"
                    "        Check the action log in the Execution Timeline panel for error details.\n"
                    "        ImageIcon placeholder is showing."
                )
            else:
                reason = "never_called"
                msg = (
                    "browser_screenshot has NEVER been called by the agent.\n"
                    "        This is the most common cause: the agent navigated to a page\n"
                    "        but forgot to capture a screenshot.\n"
                    "        ImageIcon placeholder is showing."
                )

        self._results.append(
            LayerResult(
                layer=2,
                title="Screenshot Available (State)",
                ok=False,
                message=msg,
                data={"reason": reason, "screenshot_path": path},
            )
        )

    # ------------------------------------------------------------------
    # Layer 3 — File existence on disk
    # ------------------------------------------------------------------

    def _check_file_exists(self) -> None:
        state = self._browser_state
        if not state.get("launched") or not state.get("url"):
            self._results.append(
                LayerResult(
                    layer=3,
                    title="Screenshot File on Disk",
                    ok=True,
                    message="Prerequisite not met.",
                    skipped=True,
                )
            )
            return

        path: str | None = state.get("screenshot_path")
        if not path:
            self._results.append(
                LayerResult(
                    layer=3,
                    title="Screenshot File on Disk",
                    ok=True,
                    message="No screenshot_path in state (screenshot was never taken). Nothing to check.",
                    skipped=True,
                )
            )
            return

        fp = Path(path)
        ws_path = self._workspace_path

        # 1) Absolute path
        if fp.is_absolute():
            if fp.exists():
                self._results.append(
                    LayerResult(
                        layer=3,
                        title="Screenshot File on Disk",
                        ok=True,
                        message=f"Absolute path exists: {fp} ({fp.stat().st_size} bytes)",
                        data={"resolved_path": str(fp), "size": fp.stat().st_size},
                    )
                )
            else:
                self._results.append(
                    LayerResult(
                        layer=3,
                        title="Screenshot File on Disk",
                        ok=False,
                        message=f"Absolute path NOT found: {fp}",
                        data={"expected_path": str(fp)},
                    )
                )
            return

        # 2) Relative path — resolve against workspace_path
        if ws_path:
            resolved = (ws_path / path).resolve()
            if resolved.exists():
                sz = resolved.stat().st_size
                self._results.append(
                    LayerResult(
                        layer=3,
                        title="Screenshot File on Disk",
                        ok=True,
                        message=f"Found via workspace_path: {resolved} ({sz} bytes)",
                        data={"resolved_path": str(resolved), "size": sz},
                    )
                )
                return

            # 3) Also try CWD (where the backend process actually runs)
            cwd_resolved = (Path.cwd() / path).resolve()
            if cwd_resolved.exists() and cwd_resolved != resolved:
                sz = cwd_resolved.stat().st_size
                self._results.append(
                    LayerResult(
                        layer=3,
                        title="Screenshot File on Disk",
                        ok=True,
                        message=(
                            f"Found at CWD: {cwd_resolved} ({sz} bytes)\n"
                            f"        ⚠️  PATH MISMATCH: CWD ≠ workspace_path ({ws_path})\n"
                            "        The server resolves relative paths against workspace_path,\n"
                            "        so it will look at the wrong location. This is a likely root cause!"
                        ),
                        data={
                            "resolved_path": str(cwd_resolved),
                            "size": sz,
                            "warning": "cwd_mismatch",
                        },
                    )
                )
                return

            # Not found anywhere — list candidates for debugging
            ws_outputs = sorted(ws_path.glob("outputs/browser/screenshot_*.png"))
            cwd_outputs = sorted(Path.cwd().glob("outputs/browser/screenshot_*.png"))

            msg = (
                f"File '{path}' NOT found on disk.\n"
                f"        workspace_path:  {resolved}\n"
                f"        CWD:             {cwd_resolved}"
            )
            if ws_outputs:
                preview = ", ".join(str(p.relative_to(ws_path)) for p in ws_outputs[:3])
                msg += f"\n        Found {len(ws_outputs)} screenshot(s) at workspace_path: {preview}"
            if cwd_outputs and cwd_outputs != ws_outputs:
                preview = ", ".join(str(p.relative_to(Path.cwd())) for p in cwd_outputs[:3])
                msg += f"\n        Found {len(cwd_outputs)} screenshot(s) at CWD: {preview}"

            self._results.append(
                LayerResult(
                    layer=3,
                    title="Screenshot File on Disk",
                    ok=False,
                    message=msg,
                    data={
                        "expected_workspace": str(resolved),
                        "expected_cwd": str(cwd_resolved),
                        "workspace_screenshots": len(ws_outputs),
                        "cwd_screenshots": len(cwd_outputs),
                    },
                )
            )
            return

        # No workspace_path available
        self._results.append(
            LayerResult(
                layer=3,
                title="Screenshot File on Disk",
                ok=True,
                message="Cannot resolve workspace_path — skipped file existence check.",
                skipped=True,
            )
        )

    # ------------------------------------------------------------------
    # Layer 4 — HTTP screenshot endpoint
    # ------------------------------------------------------------------

    def _check_screenshot_http(self, client: httpx.Client) -> None:
        state = self._browser_state
        if not state.get("screenshot_available"):
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=True,
                    message="Prerequisite not met — screenshot_available is false. Endpoint would return 404.",
                    skipped=True,
                )
            )
            return

        resp = self._get(client, "/api/browser/screenshot")
        if resp is None:
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message="Connection failed when fetching /api/browser/screenshot.",
                )
            )
            return

        if resp.status_code == 404:
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message=(
                        "HTTP 404 — File not found.\n"
                        "        The server cannot locate the screenshot file on disk.\n"
                        "        Likely cause: path resolution mismatch (see Layer 3)."
                    ),
                    data={"status_code": 404},
                )
            )
            return

        if resp.status_code == 403:
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message=(
                        "HTTP 403 — Forbidden.\n"
                        "        Path traversal protection triggered.\n"
                        "        The screenshot path is outside the workspace directory."
                    ),
                    data={"status_code": 403},
                )
            )
            return

        if resp.status_code != 200:
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message=f"Unexpected HTTP {resp.status_code}",
                    data={"status_code": resp.status_code},
                )
            )
            return

        ct = resp.headers.get("content-type", "")
        body_size = len(resp.content)

        if not ct.startswith("image/"):
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message=f"Wrong Content-Type: '{ct}' (expected image/png). Server may be returning HTML error page.",
                    data={"content_type": ct, "body_size": body_size},
                )
            )
            return

        if body_size < 100:
            self._results.append(
                LayerResult(
                    layer=4,
                    title="Screenshot HTTP Serve",
                    ok=False,
                    message=f"Body too small ({body_size} bytes). File may be empty or corrupted.",
                    data={"content_type": ct, "body_size": body_size},
                )
            )
            return

        self._results.append(
            LayerResult(
                layer=4,
                title="Screenshot HTTP Serve",
                ok=True,
                message=f"HTTP 200, Content-Type={ct}, {body_size:,} bytes — served correctly",
                data={"content_type": ct, "body_size": body_size},
            )
        )

    # ------------------------------------------------------------------
    # Layer 5 — Frontend visual check (Playwright)
    # ------------------------------------------------------------------

    def _check_frontend_visual(self) -> None:
        if not self._visual:
            self._results.append(
                LayerResult(
                    layer=5,
                    title="Frontend Visual Check",
                    ok=True,
                    message="Skipped — add --visual to enable Playwright frontend capture.",
                    skipped=True,
                )
            )
            return

        if not PLAYWRIGHT_AVAILABLE:
            self._results.append(
                LayerResult(
                    layer=5,
                    title="Frontend Visual Check",
                    ok=False,
                    message="Playwright not installed.\n        Run: pip install playwright && playwright install chromium",
                )
            )
            return

        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as pw:  # type: ignore[name-defined]
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()

                try:
                    page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                except Exception as exc:
                    browser.close()
                    self._results.append(
                        LayerResult(
                            layer=5,
                            title="Frontend Visual Check",
                            ok=False,
                            message=f"Cannot load frontend at {FRONTEND_URL}: {exc}",
                        )
                    )
                    return

                before_path = str(self._screenshots_dir / "viewport_before.png")
                page.screenshot(path=before_path, full_page=False)

                findings: list[str] = []

                # Detect Monitor placeholder
                if page.locator('text=等待智能体启动浏览器').count() > 0:
                    findings.append("Monitor placeholder (browser not launched)")

                # Detect Loading spinner
                if page.locator('text=浏览器启动中').count() > 0:
                    findings.append("Loading spinner (browser launching, no URL)")

                # Detect ImageIcon placeholder
                ic_divs = page.locator("div.flex.h-full.items-center.justify-center")
                has_image_icon = False
                for i in range(ic_divs.count()):
                    if ic_divs.nth(i).locator("svg").count() > 0:
                        has_image_icon = True
                        break
                if has_image_icon:
                    findings.append("ImageIcon placeholder (no screenshot available)")

                # Detect actual screenshot img
                ss_imgs = page.locator('img[alt*="截图"]')
                if ss_imgs.count() > 0:
                    findings.append(f"Actual screenshot <img> ({ss_imgs.count()} tag(s))")

                # Detect broken images
                broken_count: int = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('img'))
                        .filter(i => i.naturalWidth === 0 && i.complete).length;
                }""")
                if broken_count > 0:
                    findings.append(f"Broken image(s) detected ({broken_count} with naturalWidth=0)")

                # Detect error states
                if page.locator('text=检查后端服务').count() > 0:
                    findings.append("Error state (backend connection issue)")

                if not findings:
                    findings.append("Unknown — could not identify any known viewport element")

                status = "; ".join(findings)
                overall_ok = "Actual screenshot" in status and "Broken" not in status
                msg = f"Frontend state: {status}"

                # --trigger: type a command in the chat input
                if self._trigger:
                    chat_input = page.locator(
                        'textarea, input[type="text"], [contenteditable="true"]'
                    ).first
                    if chat_input.count() > 0:
                        try:
                            chat_input.click()
                            chat_input.fill("take a screenshot of the current page")
                            page.keyboard.press("Enter")
                            page.wait_for_timeout(8000)

                            after_path = str(self._screenshots_dir / "viewport_after.png")
                            page.screenshot(path=after_path, full_page=False)

                            after_ic = page.locator(
                                "div.flex.h-full.items-center.justify-center"
                            ).count()
                            after_img = page.locator('img[alt*="截图"]').count()

                            if after_img > 0:
                                msg += "\n        After trigger: screenshot appeared ✓"
                                overall_ok = True
                            elif after_ic > 0:
                                msg += "\n        After trigger: still showing ImageIcon (screenshot may have failed)"
                            else:
                                msg += "\n        After trigger: state changed (see screenshots/)"
                        except Exception as exc:
                            msg += f"\n        Trigger failed: {exc}"
                    else:
                        msg += "\n        --trigger: could not find chat input to type command"

                msg += f"\n        Screenshots saved to: {self._screenshots_dir}"

                browser.close()

                self._results.append(
                    LayerResult(
                        layer=5,
                        title="Frontend Visual Check",
                        ok=overall_ok,
                        message=msg,
                        data={
                            "findings": findings,
                            "screenshots_dir": str(self._screenshots_dir),
                        },
                    )
                )

        except Exception as exc:
            self._results.append(
                LayerResult(
                    layer=5,
                    title="Frontend Visual Check",
                    ok=False,
                    message=f"Playwright error: {exc}",
                )
            )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> Report:
        self._results.clear()

        # Fetch workspace_path from API
        try:
            with httpx.Client(timeout=self._timeout) as cl:
                resp = cl.get(f"{BACKEND_URL}/api/workspaces/active")
                if resp.status_code == 200:
                    ws = resp.json().get("workspace")
                    if ws and ws.get("path"):
                        self._workspace_path = Path(ws["path"])
        except Exception:
            pass

        with httpx.Client(timeout=self._timeout) as client:
            self._check_connectivity(client)

            # Layer 0 failed — stop
            if self._results and not self._results[-1].ok:
                return self._build_report()

            self._check_browser_launch()
            self._check_screenshot_available()
            self._check_file_exists()
            self._check_screenshot_http(client)

        self._check_frontend_visual()

        return self._build_report()

    def _build_report(self) -> Report:
        all_ok = all(r.ok for r in self._results)
        root_cause = self._analyze_root_cause()
        return Report(
            timestamp=datetime.now().isoformat(),
            layers=list(self._results),
            all_ok=all_ok,
            root_cause=root_cause,
            workspace_path=str(self._workspace_path) if self._workspace_path else "",
        )

    def _analyze_root_cause(self) -> str:
        issues: list[str] = []
        path_mismatch = False

        for r in self._results:
            if r.layer == 0 and not r.ok:
                issues.append(
                    "Cannot reach backend or no active workspace.\n"
                    "    → Start the backend with: npm run dev:api\n"
                    "    → Activate a workspace: uv run python main.py workspace switch <id>"
                )

        for r in self._results:
            if r.layer == 2 and not r.ok and not r.skipped:
                reason = r.data.get("reason", "")
                if reason == "never_called":
                    issues.append(
                        "The agent has NOT called browser_screenshot.\n"
                        "    → Ask the agent to 'take a screenshot of the current page'"
                    )
                elif reason == "tool_failed":
                    issues.append(
                        "browser_screenshot was called but FAILED.\n"
                        "    → Check the Execution Timeline panel in the UI for error details."
                    )
                elif reason == "TTL expired":
                    issues.append(
                        "Screenshot TTL expired (> 30 s after capture).\n"
                        "    → Screenshots only live 30 seconds. Get a NEW screenshot."
                    )
                else:
                    issues.append(r.message)

        for r in self._results:
            if r.layer == 3:
                if not r.ok:
                    if "PATH MISMATCH" in r.message or "cwd_mismatch" in str(r.data):
                        path_mismatch = True
                    else:
                        issues.append(
                            f"Screenshot file not found on disk.\n    → {r.message.split(chr(10))[0]}"
                        )
                elif "PATH MISMATCH" in r.message or "cwd_mismatch" in str(r.data):
                    path_mismatch = True

        if path_mismatch:
            ws = self._workspace_path
            issues.append(
                "Screenshot saved at CWD but server resolves from workspace_path.\n"
                f"    → CWD:  {Path.cwd()}\n"
                f"    → WS:   {ws}\n"
                "    → These must match, or the screenshot endpoint will 404.\n"
                "    → Create the workspace in the same directory where you start the backend."
            )

        for r in self._results:
            if r.layer == 4 and not r.ok:
                status = r.data.get("status_code")
                if status == 404:
                    issues.append(
                        "GET /api/browser/screenshot returned 404 (file not found).\n"
                        "    → Usually caused by the PATH MISMATCH issue in Layer 3."
                    )
                elif status == 403:
                    issues.append(
                        "GET /api/browser/screenshot returned 403 (forbidden).\n"
                        "    → Screenshot path is outside the workspace directory."
                    )
                else:
                    issues.append(f"Screenshot HTTP endpoint broken.\n    → {r.message.split(chr(10))[0]}")

        if not issues:
            return "All checks passed. The screenshot pipeline should be working correctly."

        lines: list[str] = []
        if len(issues) == 1:
            lines.append(issues[0])
        else:
            lines.append(f"{len(issues)} issues found:\n")
            for i, issue in enumerate(issues, 1):
                lines.append(f"  [{i}] {issue}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # CLI output
    # ------------------------------------------------------------------

    def print_report(self, report: Report) -> None:
        print()
        print(f"{_B}{'=' * 68}{_N}")
        print(f"  {_B}Browser Viewport Diagnostic{_N}")
        print(f"{_B}{'=' * 68}{_N}")
        print(f"  Time:       {report.timestamp[:19]}")
        print(f"  Backend:    {BACKEND_URL}")
        if self._visual:
            print(f"  Frontend:   {FRONTEND_URL}")
        if report.workspace_path:
            print(f"  Workspace:  {report.workspace_path}")
        print()

        for r in report.layers:
            tag = SKIP if r.skipped else _tag(r.ok)
            print(f"  [{tag}] L{r.layer}  {r.title}")
            for line in r.message.split("\n"):
                print(f"        {line}")
            print()

        print(f"  {_B}Root Cause{_N}")
        print(f"  {'─' * 40}")
        if report.all_ok:
            print(f"  {_G}✔ All checks passed.{_N}")
            print(f"  The screenshot pipeline appears to be working correctly.")
            print(f"  If  the  ImageIcon  placeholder  still  shows,  the  frontend")
            print(f"  may  be  in  a  stale  poll  cycle  (5 s).  Wait and refresh.")
        else:
            for line in report.root_cause.split("\n"):
                print(f"  {line}")

        print(f"\n{_B}{'=' * 68}{_N}")

        # Save JSON
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self._output_dir / f"browser_viewport_report_{ts}.json"
        payload = {
            "timestamp": report.timestamp,
            "all_ok": report.all_ok,
            "root_cause": report.root_cause,
            "workspace_path": report.workspace_path,
            "layers": [
                {
                    "layer": r.layer,
                    "title": r.title,
                    "ok": r.ok,
                    "skipped": r.skipped,
                    "message": r.message,
                    "data": r.data,
                }
                for r in report.layers
            ],
        }
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Report:      {report_path}")

        pngs = sorted(self._screenshots_dir.glob("*.png"))
        if pngs:
            print(f"  Screenshots: {self._screenshots_dir}/")
            for f in pngs:
                print(f"    {f.name}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="诊断 BrowserViewport 为何显示占位符而非浏览器截图",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="用 Playwright 打开前端页面进行视觉检测 (Layer 5)",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="视觉检测时尝试通过聊天框触发 browser_screenshot (需 --visual)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP 请求超时秒数 (default: 10)",
    )
    args = parser.parse_args()

    if args.trigger and not args.visual:
        print(f"  {_Y}⚠{_N}  --trigger requires --visual; enabling --visual automatically.")
        args.visual = True

    diag = BrowserViewportDiagnostic(
        visual=args.visual,
        trigger=args.trigger,
        timeout=args.timeout,
    )
    report = diag.run()
    diag.print_report(report)
    sys.exit(0 if report.all_ok else 1)


if __name__ == "__main__":
    main()
